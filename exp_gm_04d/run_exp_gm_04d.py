#!/usr/bin/env python3
"""EXP-GM-04d protocol retest. Pilot = development 45-equivalent, new cells only for mismatches_patch_v1."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04b.versioning import parse_artifact_spec_version
from exp_gm_04c.scoring import r0_ok
from exp_gm_04d.loop import run_cell_loop
from exp_gm_04d.roles import executor_prompt, parse_review_json, reviewer_prompt, rule_executor, rule_reviewer, wrap_reviewer_output
from exp_gm_04d.scoring import first_error, process_success
from exp_gm_04d.tasks import DEV_TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "exp_gm_04d_protocol_retest"
EXECUTOR_ID = 5
REVIEWER_ID = 6
FROZEN_04C = BRIDGE_ROOT / "output" / "exp_gm_04c_20260824"


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


def _llm_reviewer(task: dict):
    def _fn(draft: str, private: dict):
        raw = _llm(reviewer_prompt(draft, private))
        try:
            parsed = parse_review_json(raw)
        except (ValueError, json.JSONDecodeError):
            parsed = {"raw": raw}
        return wrap_reviewer_output(parsed, private)

    return _fn


def _rule_pair(task: dict):
    def executor(brief: str, review):
        version = "v2" if review and review.get("decision") == "revise" else "v1"
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
        reviewer_fn = _llm_reviewer(task)
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
        review_contract_ok=bool(action.get("decision") in {"approve", "revise"}) and loop.get("freeze_ok") is not False,
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
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0", detail=r0_detail),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("oracle_present", task[expected_version]["oracle"].is_file(), layer="R0"),
        ],
        artifact_gates=[
            GateResult("final_exists", exists, layer="R1"),
            GateResult("reviewer_did_not_write", not loop.get("reviewer_wrote_artifact"), layer="R1"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="pytest_hidden",
                evaluable=expected_oracle["evaluable"],
                score=1.0 if target_correct else 0.0,
                passed=target_correct,
                critical=False,
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="review_loop",
                evaluable=True,
                score=1.0 if conditioned else 0.0,
                passed=conditioned,
                critical=True,
            ),
        ],
        process_profile={"first_error": err, "events": events},
        extra={
            "task_id": task["id"],
            "split": task.get("split") or "development",
            "track": track,
            "variant": variant,
            "seed": seed,
            "mode": mode,
            "protocol": "mismatches_patch_v1",
            "model_version": "rule" if mode == "rule" else "GLM-4-Flash",
            "target_correct": target_correct,
            "oracle_conditioned_success": conditioned,
            "review_advice_correct": loop.get("review_advice_correct"),
            "review_decision": action.get("decision"),
            "false_positive_revision": loop.get("false_positive_revision"),
            "patch_adoption": loop.get("patch_adoption"),
            "freeze_ok": loop.get("freeze_ok"),
            "applied_patch_ids": (loop.get("final_inspect") or {}).get("applied_patch_ids"),
            "elapsed_s": elapsed,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cell


def _fp_rate(cells: list[dict]) -> float | None:
    subset = [
        c for c in cells
        if (c.get("extra") or {}).get("track") == "full_review"
        and (c.get("extra") or {}).get("variant") == "control"
        and c.get("measurement_valid")
    ]
    if not subset:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get("false_positive_revision"))) for c in subset) / len(subset), 4)


def _adopt_rate(cells: list[dict]) -> float | None:
    subset = [
        c for c in cells
        if (c.get("extra") or {}).get("track") == "full_review"
        and (c.get("extra") or {}).get("variant") == "intervention"
        and (c.get("extra") or {}).get("review_advice_correct") is True
        and c.get("measurement_valid")
    ]
    if not subset:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get("patch_adoption"))) for c in subset) / len(subset), 4)


def load_legacy_04c() -> list[dict]:
    cells: list[dict] = []
    runs = FROZEN_04C / "runs"
    if not runs.is_dir():
        return cells
    for path in sorted(runs.glob("*/cell_result.json")):
        cell = json.loads(path.read_text(encoding="utf-8"))
        extra = cell.setdefault("extra", {})
        if extra.get("track") != "full_review":
            continue
        extra["protocol"] = "legacy_frozen"
        extra["split"] = "development"
        profile = cell.get("process_profile") or {}
        decision = extra.get("review_decision") or profile.get("review_decision")
        advice = extra.get("review_advice_correct")
        if advice is None:
            advice = profile.get("review_advice_correct")
        extra["review_decision"] = decision
        extra["review_advice_correct"] = advice
        extra["false_positive_revision"] = extra.get("variant") == "control" and decision == "revise"
        extra["patch_adoption"] = bool(
            extra.get("variant") == "intervention" and advice and extra.get("oracle_conditioned_success")
        )
        extra["review_delivered"] = True
        cells.append(cell)
    return cells


def _pack(cells: list[dict], out: Path, *, phase: str) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    new_cells = [c for c in cells if (c.get("extra") or {}).get("protocol") == "mismatches_patch_v1"]
    old_cells = [c for c in cells if (c.get("extra") or {}).get("protocol") == "legacy_frozen"]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-04d",
        "phase": phase,
        "ranking_eligible": False,
        "summary": summary,
        "false_positive_revision_rate_new": _fp_rate(new_cells),
        "false_positive_revision_rate_old": _fp_rate(old_cells),
        "patch_adoption_rate_new": _adopt_rate(new_cells),
        "patch_adoption_rate_old": _adopt_rate(old_cells),
    }
    fp_old, fp_new = payload["false_positive_revision_rate_old"], payload["false_positive_revision_rate_new"]
    ad_old, ad_new = payload["patch_adoption_rate_old"], payload["patch_adoption_rate_new"]
    payload["protocol_gain_fp"] = None if fp_old is None or fp_new is None else round(fp_old - fp_new, 4)
    payload["protocol_gain_adopt"] = None if ad_old is None or ad_new is None else round(ad_new - ad_old, 4)
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# EXP-GM-04d Protocol Retest",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 状态：pilot，不可排名",
        "- 开发集：工资/返还/预算；留出题未参与协议设计",
        "- 旧协议来自冻结的 04c Full 格，不在同一 54 格上重训",
        "",
        "## 04d-A 错误修改",
        "",
        f"- FalsePositiveRevisionRate 旧：{fp_old}",
        f"- FalsePositiveRevisionRate 新：{fp_new}",
        f"- ProtocolGain (旧−新，越大越好)：{payload['protocol_gain_fp']}",
        "",
        "## 04d-B 意见采用",
        "",
        f"- PatchAdoptionRate 旧：{ad_old}",
        f"- PatchAdoptionRate 新：{ad_new}",
        f"- ProtocolGain (新−旧，越大越好)：{payload['protocol_gain_adopt']}",
        "",
        "| instance | protocol | variant | track | valid | FullPass | FP | adopt | first_error |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        report.append(
            f"| {cell.get('instance_id')} | {extra.get('protocol')} | {extra.get('variant')} | "
            f"{extra.get('track')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('false_positive_revision')} | {extra.get('patch_adoption')} | "
            f"{(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def run_pilot(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    plan = []
    for task in DEV_TASKS:
        for seed in seeds:
            plan.append((task, "control", "full_review", seed))
            plan.append((task, "intervention", "full_review", seed))
            plan.append((task, "intervention", "drop_review", seed))
    for task, variant, track, seed in plan:
        print(f"run {task['id']} {variant} {track} s{seed} mode={mode}", flush=True)
        cell = _score_cell(task, variant, track, seed, out, mode=mode)
        cells.append(cell)
        extra = cell.get("extra") or {}
        print(
            f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
            f"fp={extra.get('false_positive_revision')} adopt={extra.get('patch_adoption')} "
            f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
            flush=True,
        )
    return cells


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    _pin_glm()
    out = BRIDGE_ROOT / "output" / "exp_gm_04d_20260824"
    out.mkdir(parents=True, exist_ok=True)
    print("phase=pilot-dev", flush=True)
    cells = load_legacy_04c()
    cells.extend(run_pilot(out, [0, 1, 2], mode="llm"))
    payload = _pack(cells, out, phase="pilot_dev")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    valid_new = sum(
        1 for c in cells
        if (c.get("extra") or {}).get("protocol") == "mismatches_patch_v1" and c.get("measurement_valid")
    )
    if valid_new < 27:
        print(f"pilot 新协议可评分 {valid_new} < 27，停止留出题。", flush=True)
        return 1
    print("pilot 过门。留出题需显式再跑。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
