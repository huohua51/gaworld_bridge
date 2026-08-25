#!/usr/bin/env python3
"""EXP-GM-04c: Reviewer—Executor loop. Seed 0 first; more repeats only if R0 holds."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04b.versioning import parse_artifact_spec_version
from exp_gm_04c.loop import run_cell_loop
from exp_gm_04c.roles import executor_prompt, parse_review_json, reviewer_prompt, rule_executor, rule_reviewer
from exp_gm_04c.scoring import first_error, process_success, r0_ok
from exp_gm_04c.tasks import TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "exp_gm_04c_task_w1_review_loop"
TRACKS = ("focused", "full_review", "drop_review")
VARIANTS = ("control", "intervention")
EXECUTOR_ID = 5
REVIEWER_ID = 6


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault("paratera_glm", {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 2048)
        glm["temperature"] = 0
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = "paratera_glm"
    tasks = dict(routing.get("tasks") or {})
    tasks["schedule"] = "paratera_glm"
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = "paratera_glm"


def _llm(prompt: str) -> str:
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _llm_executor(out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.schemas import WorkBrief

    n = {"i": 0}

    def _fn(brief_text: str, review):
        n["i"] += 1
        brief = WorkBrief(
            task_id=f"exec_{n['i']}",
            agent_id=EXECUTOR_ID,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="编写 Python 脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=executor_prompt(brief_text, review),
            estimated_minutes=15,
            submitted_at=time.time(),
        )
        ctx = AdapterContext(artifacts_root=str(out_dir / "adapter_calls"), llm=_llm, config={})
        result = CodeAdapter().run(brief, ctx)
        paths = result.artifact_paths or []
        if not paths or not os.path.isfile(paths[0]):
            return ""
        return Path(paths[0]).read_text(encoding="utf-8")

    return _fn


def _llm_reviewer():
    def _fn(draft: str, private: dict):
        raw = _llm(reviewer_prompt(draft, private))
        try:
            return parse_review_json(raw)
        except (ValueError, json.JSONDecodeError):
            return {"raw": raw}

    return _fn


def _rule_pair(task: dict):
    def executor(brief: str, review):
        version = "v2" if ("70000" in brief or "返还率 0.5" in brief or "总预算 80" in brief) else "v1"
        return rule_executor(task, version=version, review=review)

    def reviewer(draft: str, private: dict):
        return rule_reviewer(draft, task, private)

    return executor, reviewer


def _score_cell(task: dict, variant: str, track: str, seed: int, out_root: Path, *, mode: str) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    cfg = CONFIG
    cfg.setdefault("eval_mode", {})
    cfg["eval_mode"]["enabled"] = True
    apply_eval_mode_runtime(cfg)

    instance_id = f"{task['id']}_{variant}_{track}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    if mode == "rule":
        executor_fn, reviewer_fn = _rule_pair(task)
    else:
        executor_fn = _llm_executor(run_dir)
        reviewer_fn = _llm_reviewer()
    started = time.time()
    loop = run_cell_loop(
        task=task,
        variant=variant,
        track=track,
        task_id=instance_id,
        out_dir=run_dir,
        executor_fn=executor_fn,
        reviewer_fn=reviewer_fn,
        brief_v1=task["v1"]["brief"],
        brief_v2=task["v2"]["brief"],
        executor_id=EXECUTOR_ID,
        reviewer_id=REVIEWER_ID,
    )
    elapsed = round(time.time() - started, 3)
    expected_version = loop["expected_version"]
    artifact = loop["final_path"]
    expected_oracle = score_hidden_tests(artifact, task[expected_version]["oracle"])
    other_version = "v2" if expected_version == "v1" else "v1"
    other_oracle = score_hidden_tests(artifact, task[other_version]["oracle"])
    artifact_spec = parse_artifact_spec_version(artifact)
    exists = bool(artifact and os.path.isfile(artifact))
    target_correct = bool(expected_oracle["passed"] and exists)
    other_also = bool(other_oracle.get("passed"))
    r0, r0_detail = r0_ok(track, variant, loop)
    events = list(loop["events"])
    action = loop.get("review_action") or {}
    stale_final = bool(
        variant == "intervention"
        and track == "full_review"
        and (loop.get("final_inspect") or {}).get("spec_version") == "v1"
    )
    err = first_error(
        track=track,
        variant=variant,
        events=events,
        draft_exists=bool(loop.get("draft_path") and os.path.isfile(str(loop.get("draft_path") or ""))),
        final_exists=exists,
        review_emitted="review_emitted" in events,
        review_contract_ok=bool(action.get("decision") in {"approve", "revise"}),
        review_delivered="review_delivered" in events,
        review_read="review_read" in events,
        review_adopted="review_adopted" in events,
        review_advice_correct=loop.get("review_advice_correct"),
        private_ok=bool(loop.get("private_ok")),
        unauthorized_write=bool(loop.get("reviewer_wrote_artifact")),
        stale_final=stale_final,
        target_correct=target_correct,
        absorbed="absorb" in events,
    )
    conditioned = process_success(track, variant, loop, target_correct=target_correct, other_also=other_also)
    measurement = [
        GateResult("execution_valid", r0, layer="R0", detail=r0_detail),
        GateResult("eval_mode_on", True, layer="R0"),
        GateResult("v2_isolated", not loop.get("leak_on_first_brief"), layer="R0", detail=str(loop.get("leak_on_first_brief"))),
        GateResult("oracle_present", task[expected_version]["oracle"].is_file(), layer="R0"),
    ]
    artifact_gates = [
        GateResult("final_exists", exists, layer="R1", detail=str(artifact)),
        GateResult("draft_from_executor", track == "focused" or bool(loop.get("draft_path")), layer="R1"),
        GateResult("reviewer_did_not_write", not loop.get("reviewer_wrote_artifact"), layer="R1"),
    ]
    criteria = [
        CriterionResult(
            criterion_id="target_correct",
            layer="R2",
            scorer="pytest_hidden",
            evaluable=expected_oracle["evaluable"],
            score=1.0 if target_correct else 0.0,
            passed=target_correct,
            critical=False,
            evidence_ids=[artifact] if artifact else [],
            detail=expected_oracle.get("stdout_tail", "")[:400],
        ),
        CriterionResult(
            criterion_id="oracle_conditioned_success",
            layer="R3",
            scorer="review_loop",
            evaluable=True,
            score=1.0 if conditioned else 0.0,
            passed=conditioned,
            critical=True,
            detail=(
                f"input_final={artifact_spec} expected={expected_version} "
                f"advice={loop.get('review_advice_correct')} other_also={other_also}"
            ),
        ),
    ]
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=measurement,
        artifact_gates=artifact_gates,
        criteria=criteria,
        process_profile={
            "first_error": err,
            "events": events,
            "review_requested": "review_requested" in events,
            "review_emitted": "review_emitted" in events,
            "review_delivered": "review_delivered" in events,
            "review_read": "review_read" in events,
            "review_adopted": "review_adopted" in events,
            "artifact_reworked": "executor_rework" in events,
            "final_verified": target_correct,
            "review_advice_correct": loop.get("review_advice_correct"),
            "review_decision": action.get("decision"),
            "input_spec_version": "v2" if track == "focused" and variant == "intervention" else "v1",
            "artifact_spec_version": artifact_spec,
            "executor_calls": loop.get("executor_calls"),
            "reviewer_calls": loop.get("reviewer_calls"),
        },
        extra={
            "task_id": task["id"],
            "track": track,
            "variant": variant,
            "seed": seed,
            "mode": mode,
            "run_id": instance_id,
            "model_version": "rule" if mode == "rule" else "GLM-4-Flash",
            "temperature": 0,
            "expected_version": expected_version,
            "oracle_expected": expected_oracle,
            "oracle_other": other_oracle,
            "target_correct": target_correct,
            "oracle_conditioned_success": conditioned,
            "other_version_also_passes": other_also,
            "elapsed_s": elapsed,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(
        json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return cell


def _rate(cells: list[dict], track: str, variant: str | None = None) -> float | None:
    subset = [
        c
        for c in cells
        if c.get("extra", {}).get("track") == track
        and (variant is None or c.get("extra", {}).get("variant") == variant)
        and c.get("full_pass") is not None
    ]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _decision(rates: dict) -> str:
    f = rates.get("focused")
    full = rates.get("full_review")
    drop_i = rates.get("drop_intervention")
    full_i = rates.get("full_intervention")
    if any(v is None for v in (f, full, drop_i, full_i)):
        return "出现不可评分。先看 R0，停止协作能力解释。"
    if f >= 0.8 and full >= 0.8 and drop_i <= 0.4:
        return "Focused 高、Full 高、Drop 干预低：审核闭环有效，且审核信息有价值。"
    if f >= 0.8 and full_i < 0.5:
        return "Focused 高、Full 干预低：看 Rule Full。Rule 高则是模型协作失败；Rule 也低则进入平台修复。"
    if f < 0.5 and full < 0.5:
        return "Focused 和 Full 都低：先检查任务、brief 或 Executor 能力。"
    if full_i >= 0.8 and drop_i >= 0.8:
        return "Full 和 Drop 干预都高：存在信息泄漏、任务过简单，或 v1/v2 没有真正区分。"
    return "结果混合。按逐格 first_error 和 review_advice_correct 拆开 Reviewer / 路由 / Executor。"


def _render(payload: dict) -> str:
    lines = [
        "# EXP-GM-04c TASK-W1-review-loop Pilot",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 状态：pilot，不可排名",
        "- 路线：04a 正控通过 → 04b M4 传播通过 → 无平台首错，不进修复分支 → 04c",
        "- v2 只进入 Reviewer 私有上下文；Executor 初始只持有 v1",
        "- FullPass 要求 oracle_conditioned_success，碰巧过线或未采用 Review 不算干净成功",
        "",
        "## 覆盖与主结果",
        "",
        f"- requested：{payload['summary']['requested']}",
        f"- measurement_valid：{payload['summary']['measurement_valid']}",
        f"- coverage：{payload['summary']['coverage']}",
        f"- oracle_conditioned FullPass Rate：{payload['summary']['full_pass_rate']}",
        f"- target_correct Rate：{payload['target_correct_rate']}",
        "",
        "### 分轨",
        "",
        f"- Focused：{payload['rates']['focused']}（control {payload['rates']['focused_control']} / intervention {payload['rates']['focused_intervention']}）",
        f"- Full review：{payload['rates']['full_review']}（control {payload['rates']['full_control']} / intervention {payload['rates']['full_intervention']}）",
        f"- Drop-review：{payload['rates']['drop_review']}（control {payload['rates']['drop_control']} / intervention {payload['rates']['drop_intervention']}）",
        f"- ReviewValue (Full − Drop)：{payload['review_value']}",
        f"- ReviewValue intervention only：{payload['review_value_intervention']}",
        f"- ReviewPropagationGap (Focused − Full)：{payload['review_propagation_gap']}",
        "",
        "## 决策",
        "",
        payload["decision"],
        "",
        "| instance | valid | FullPass | target_correct | oracle_conditioned | first_error | advice |",
        "|---|---|---|---|---|---|---|",
    ]
    for cell in payload["summary"]["cells"]:
        extra = cell.get("extra") or {}
        profile = cell.get("process_profile") or {}
        lines.append(
            "| {instance_id} | {valid} | {full_pass} | {target_correct} | {conditioned} | {first_error} | {advice} |".format(
                instance_id=cell.get("instance_id"),
                valid=cell.get("measurement_valid"),
                full_pass=cell.get("full_pass"),
                target_correct=extra.get("target_correct"),
                conditioned=extra.get("oracle_conditioned_success"),
                first_error=profile.get("first_error"),
                advice=profile.get("review_advice_correct"),
            )
        )
    return "\n".join(lines) + "\n"


def _pack(cells: list[dict], out: Path, *, phase: str) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    scored = [c for c in cells if c.get("full_pass") is not None]
    target_rate = (
        round(sum(int(bool((c.get("extra") or {}).get("target_correct"))) for c in scored) / len(scored), 4)
        if scored
        else None
    )
    rates = {
        "focused": _rate(cells, "focused"),
        "full_review": _rate(cells, "full_review"),
        "drop_review": _rate(cells, "drop_review"),
        "focused_control": _rate(cells, "focused", "control"),
        "focused_intervention": _rate(cells, "focused", "intervention"),
        "full_control": _rate(cells, "full_review", "control"),
        "full_intervention": _rate(cells, "full_review", "intervention"),
        "drop_control": _rate(cells, "drop_review", "control"),
        "drop_intervention": _rate(cells, "drop_review", "intervention"),
    }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-04c",
        "task_id": "TASK-W1-review-loop",
        "status": "pilot",
        "ranking_eligible": False,
        "phase": phase,
        "summary": summary,
        "target_correct_rate": target_rate,
        "rates": rates,
        "review_value": None if rates["full_review"] is None or rates["drop_review"] is None else round(rates["full_review"] - rates["drop_review"], 4),
        "review_value_intervention": None if rates["full_intervention"] is None or rates["drop_intervention"] is None else round(rates["full_intervention"] - rates["drop_intervention"], 4),
        "review_propagation_gap": None if rates["focused"] is None or rates["full_review"] is None else round(rates["focused"] - rates["full_review"], 4),
        "decision": "",
    }
    payload["decision"] = _decision(rates)
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "REPORT.md").write_text(_render(payload), encoding="utf-8")
    return payload


def run_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in TASKS:
        for variant in VARIANTS:
            for track in TRACKS:
                for seed in seeds:
                    print(f"run {task['id']} variant={variant} track={track} seed={seed} mode={mode}", flush=True)
                    cell = _score_cell(task, variant, track, seed, out, mode=mode)
                    cells.append(cell)
                    extra = cell.get("extra") or {}
                    print(
                        f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                        f"target_correct={extra.get('target_correct')} "
                        f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                        flush=True,
                    )
    return cells


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    _pin_glm()
    out = BRIDGE_ROOT / "output" / "exp_gm_04c_20260824"
    out.mkdir(parents=True, exist_ok=True)
    print("phase=seed0", flush=True)
    cells = run_matrix(out, [0], mode="llm")
    payload = _pack(cells, out, phase="seed0")
    print(_render(payload))
    if payload["summary"]["coverage"] < 1.0 or payload["summary"]["measurement_valid"] < 18:
        print("seed0 未过测量门，停止补重复。", flush=True)
        return 1
    print("phase=repeats", flush=True)
    cells.extend(run_matrix(out, [1, 2], mode="llm"))
    payload = _pack(cells, out, phase="all")
    print(_render(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
