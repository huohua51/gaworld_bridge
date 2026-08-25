#!/usr/bin/env python3
"""EXP-GM-04b: TASK-W1-revision Focused vs Pipeline × control vs intervention.

3 tasks × 2 variants × 2 tracks × 3 repeats = 36 cells.
Unique mechanism change is the execution track. Ranking is off.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04b.tasks import TASKS
from exp_gm_04b.versioning import first_error, parse_artifact_spec_version
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "exp_gm_04b_task_w1_revision"
SEEDS = [0, 1, 2]
TRACKS = ("focused", "pipeline")
VARIANTS = ("control", "intervention")
AGENT_ID = 5


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
    from llm_providers import LLMRouter
    from config import CONFIG

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _brief(task_id: str, brief_text: str, spec_version: str, seed: int, track: str, variant: str):
    from gaworld.work.schemas import WorkBrief

    return WorkBrief(
        task_id=f"{task_id}_{variant}_{track}_s{seed}",
        agent_id=AGENT_ID,
        sim_day=1,
        sim_time="10:00",
        activity="工作",
        chosen_action="编写 Python 脚本实现指定函数",
        deliverable="py_script",
        adapter="code",
        brief_text=brief_text,
        estimated_minutes=15,
        submitted_at=time.time(),
        spec_version=spec_version,
    )


def _run_adapter(brief, out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter

    ctx = AdapterContext(artifacts_root=str(out_dir / "artifacts"), llm=_llm, config={})
    return CodeAdapter().run(brief, ctx)


def _run_focused(brief, out_dir: Path):
    result = _run_adapter(brief, out_dir)
    events = ["adapter_run"]
    if result.artifact_paths:
        events.append("artifact_written")
    return {
        "result": result,
        "events": events,
        "producer": "adapter",
        "input_spec_version": brief.spec_version,
        "claim_spec_version": None,
        "revision": None,
        "delivered_version": brief.spec_version,
    }


def _run_pipeline(brief_v1, brief_v2, variant: str, out_dir: Path, agent: dict):
    from gaworld.work.ingest import absorb_completed_for
    from gaworld.work.queue import WorkQueue

    queue = WorkQueue(str(out_dir / "queue.jsonl"))
    events = ["queue_submit"]
    queue.submit(brief_v1)
    claimed = queue.claim_next()
    if claimed is None:
        from gaworld.work.adapters.base import make_failed

        failed = make_failed(brief_v1, "claim returned no brief", time.time())
        return {
            "result": failed,
            "events": events + ["pipeline_empty"],
            "producer": "work_pipeline",
            "input_spec_version": None,
            "claim_spec_version": None,
            "revision": None,
            "delivered_version": None,
        }
    events.append("queue_claim")
    claim_version = getattr(claimed, "spec_version", "v1")
    revision = None
    if variant == "intervention":
        events.append("requirement_revision")
        revision = queue.revise(brief_v1.task_id, brief_text=brief_v2.brief_text, spec_version="v2")
        if revision.get("ok"):
            events.append("revision_delivered")
    latest = queue.get_brief(brief_v1.task_id) or claimed
    events.append("adapter_run")
    result = _run_adapter(latest, out_dir)
    from gaworld.work.schemas import WorkResult

    if isinstance(result, WorkResult):
        queue.record_result(result)
        events.append("queue_result")
    absorbed = absorb_completed_for(
        agent, queue=queue, market=None, sim_day=1, sim_time="10:00", limit=5
    )
    if absorbed:
        events.append("absorb")
        result = absorbed[0]
    return {
        "result": result,
        "events": events,
        "producer": "work_pipeline",
        "input_spec_version": getattr(latest, "spec_version", None),
        "claim_spec_version": claim_version,
        "revision": revision,
        "delivered_version": getattr(latest, "spec_version", None),
    }


def _score_cell(task: dict, variant: str, track: str, seed: int, out_root: Path) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    cfg = CONFIG
    cfg.setdefault("eval_mode", {})
    cfg["eval_mode"]["enabled"] = True
    apply_eval_mode_runtime(cfg)

    expected_version = "v1" if variant == "control" else "v2"
    instance_id = f"{task['id']}_{variant}_{track}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    brief_v1 = _brief(task["id"], task["v1"]["brief"], "v1", seed, track, variant)
    brief_v2 = _brief(task["id"], task["v2"]["brief"], "v2", seed, track, variant)
    focused_brief = brief_v1 if variant == "control" else brief_v2
    agent = {
        "id": AGENT_ID,
        "name": "王思远",
        "job": "产品经理",
        "state": {"emotion": 0.6, "stress": 0.4, "econ_security": 0.5},
        "memory": [],
    }
    started = time.time()
    if track == "focused":
        run = _run_focused(focused_brief, run_dir)
    else:
        run = _run_pipeline(brief_v1, brief_v2, variant, run_dir, agent)
    elapsed = round(time.time() - started, 3)

    result = run["result"]
    events = list(run["events"])
    paths = list(result.artifact_paths or [])
    artifact = paths[0] if paths else None
    expected_oracle = score_hidden_tests(artifact, task[expected_version]["oracle"])
    other_version = "v2" if expected_version == "v1" else "v1"
    other_oracle = score_hidden_tests(artifact, task[other_version]["oracle"])
    artifact_spec_version = parse_artifact_spec_version(artifact)
    input_spec_version = run["input_spec_version"]
    adapter_ok = result.status == "ok"
    exists = bool(artifact and os.path.isfile(artifact))
    n_tests = int(task["n_tests"])
    pass_rate = (expected_oracle["pass_count"] / n_tests) if expected_oracle["evaluable"] and n_tests else 0.0
    target_correct = bool(expected_oracle["passed"] and exists and adapter_ok)
    other_also = bool(other_oracle.get("passed"))
    revision = run["revision"] or {}
    revision_emitted = variant == "intervention" and track == "pipeline" and "requirement_revision" in events
    revision_ok = bool(revision.get("ok"))
    if track == "focused":
        revision_emitted = False
        revision_ok = True
    oracle_conditioned = bool(
        target_correct
        and input_spec_version == expected_version
        and artifact_spec_version == expected_version
        and not other_also
    )
    err = first_error(
        track=track,
        variant=variant,
        expected_version=expected_version,
        revision_emitted=revision_emitted if variant == "intervention" and track == "pipeline" else True,
        revision_ok=revision_ok if variant == "intervention" and track == "pipeline" else True,
        delivered_version=run["delivered_version"],
        input_spec_version=input_spec_version,
        artifact_spec_version=artifact_spec_version,
        artifact_exists=exists,
        adapter_ok=adapter_ok,
        target_correct=target_correct,
        other_version_also_passes=other_also,
        absorbed="absorb" in events,
        oracle_first_error=expected_oracle.get("first_error"),
    )

    revise_count = 1 if revision else 0
    revise_before_adapter = (
        "requirement_revision" in events
        and events.index("requirement_revision") < events.index("adapter_run")
        if "requirement_revision" in events and "adapter_run" in events
        else variant != "intervention" or track != "pipeline"
    )
    control_clean = variant != "control" or revise_count == 0
    r0_ok = bool(exists is not None and revise_before_adapter and control_clean)
    if track == "pipeline" and variant == "intervention":
        r0_ok = r0_ok and revise_count == 1 and "queue_claim" in events and "adapter_run" in events
    if track == "pipeline" and variant == "control":
        r0_ok = r0_ok and revise_count == 0 and "queue_claim" in events and "adapter_run" in events
    if track == "focused":
        r0_ok = r0_ok and revise_count == 0 and "adapter_run" in events

    measurement = [
        GateResult("execution_valid", r0_ok, layer="R0", detail=f"track={track} variant={variant} elapsed={elapsed}s"),
        GateResult("eval_mode_on", True, layer="R0", detail="eval_mode.enabled"),
        GateResult("revision_timing", revise_before_adapter, layer="R0", detail=str(events)),
        GateResult("control_has_no_revision", control_clean, layer="R0"),
        GateResult("oracle_present", task[expected_version]["oracle"].is_file(), layer="R0"),
    ]
    artifact_gates = [
        GateResult("artifact_exists", exists and adapter_ok, layer="R1", detail=str(paths)),
        GateResult("producer_is_agent_adapter", run["producer"] in {"adapter", "work_pipeline"}, layer="R1"),
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
            evidence_ids=paths,
            detail=expected_oracle.get("stdout_tail", "")[:400],
        ),
        CriterionResult(
            criterion_id="hidden_test_pass_rate",
            layer="R2",
            scorer="pytest_hidden",
            evaluable=expected_oracle["evaluable"],
            score=round(pass_rate, 4),
            passed=expected_oracle["passed"],
            critical=False,
            detail=f"{expected_oracle['pass_count']}/{n_tests}",
        ),
        CriterionResult(
            criterion_id="oracle_conditioned_success",
            layer="R3",
            scorer="version_bind",
            evaluable=True,
            score=1.0 if oracle_conditioned else 0.0,
            passed=oracle_conditioned,
            critical=True,
            detail=(
                f"input={input_spec_version} artifact={artifact_spec_version} "
                f"expected={expected_version} other_also={other_also}"
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
            "producer": run["producer"],
            "absorb_occurred": "absorb" in events,
            "input_spec_version": input_spec_version,
            "artifact_spec_version": artifact_spec_version,
            "claim_spec_version": run["claim_spec_version"],
            "delivered_version": run["delivered_version"],
        },
        extra={
            "task_id": task["id"],
            "track": track,
            "variant": variant,
            "seed": seed,
            "run_id": instance_id,
            "model_version": "GLM-4-Flash",
            "temperature": 0,
            "mechanism_condition": f"{track}:{variant}",
            "expected_version": expected_version,
            "adapter_status": result.status,
            "adapter_error": result.error,
            "oracle_expected": expected_oracle,
            "oracle_other": other_oracle,
            "revision": revision,
            "elapsed_s": elapsed,
            "target_correct": target_correct,
            "oracle_conditioned_success": oracle_conditioned,
            "other_version_also_passes": other_also,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(
        json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return cell


def _group_rates(cells: list[dict], track: str, variant: str) -> float | None:
    subset = [
        c
        for c in cells
        if c.get("extra", {}).get("track") == track
        and c.get("extra", {}).get("variant") == variant
        and c.get("full_pass") is not None
    ]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _pair_rows(cells: list[dict]) -> list[dict]:
    rows = []
    for task in TASKS:
        for variant in VARIANTS:
            for seed in SEEDS:
                pair = {
                    c["extra"]["track"]: c
                    for c in cells
                    if c.get("extra", {}).get("task_id") == task["id"]
                    and c.get("extra", {}).get("variant") == variant
                    and c.get("extra", {}).get("seed") == seed
                }
                focused = pair.get("focused")
                pipeline = pair.get("pipeline")
                if not focused or not pipeline:
                    continue
                f_ok = int(focused.get("full_pass") or 0) if focused.get("measurement_valid") else None
                p_ok = int(pipeline.get("full_pass") or 0) if pipeline.get("measurement_valid") else None
                rows.append(
                    {
                        "task_id": task["id"],
                        "variant": variant,
                        "seed": seed,
                        "focused": f_ok,
                        "pipeline": p_ok,
                        "epg": None if f_ok is None or p_ok is None else f_ok - p_ok,
                        "focused_first_error": (focused.get("process_profile") or {}).get("first_error"),
                        "pipeline_first_error": (pipeline.get("process_profile") or {}).get("first_error"),
                        "focused_input": (focused.get("process_profile") or {}).get("input_spec_version"),
                        "pipeline_input": (pipeline.get("process_profile") or {}).get("input_spec_version"),
                        "focused_artifact": (focused.get("process_profile") or {}).get("artifact_spec_version"),
                        "pipeline_artifact": (pipeline.get("process_profile") or {}).get("artifact_spec_version"),
                    }
                )
    return rows


def _decision(payload: dict) -> str:
    f_c = payload["rates"]["focused_control"]
    f_i = payload["rates"]["focused_intervention"]
    p_c = payload["rates"]["pipeline_control"]
    p_i = payload["rates"]["pipeline_intervention"]
    if any(v is None for v in (f_c, f_i, p_c, p_i)):
        return "出现不可评分或事件缺失（R0）。先修 Trace 和 Runner，停止能力解释。"
    if f_c >= 0.8 and f_i >= 0.8 and p_c >= 0.8 and p_i < 0.5:
        return "Focused 两格都高，Pipeline 干预低：Agent 能做，GAWorld 没有传播最新需求。下一步改队列版本、事件订阅或重新执行机制。"
    if f_i < 0.5 and p_i < 0.5:
        return "Focused 和 Pipeline 干预都低：任务说明、模型或 Adapter 本身有问题。不改 GAWorld 流程，先校准 brief 和任务。"
    if f_c >= 0.8 and p_c >= 0.8 and f_i < 0.5 and p_i < 0.5:
        return "两轨 control 高、intervention 都锁旧值：模型或 Adapter 没有处理状态修订。增加最新状态覆盖和版本绑定。"
    if min(f_c, f_i, p_c, p_i) >= 0.8:
        return "两轨全部高：当前单执行器修订链也不是瓶颈。可以进入 EXP-GM-04c（Reviewer—Executor 审核闭环）。"
    return "结果混合，按逐格 first_error 定位，不要先做完整 TASK-W1。"


def _render(payload: dict) -> str:
    lines = [
        "# EXP-GM-04b TASK-W1-revision Pilot",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 状态：pilot，不可排名",
        "- 对照：Focused=直接给最终有效版本 vs Pipeline=`submit(v1)→claim→revise(v2)→adapter`",
        "- control 按 v1 隐藏测试验收；intervention 按 v2 验收",
        "- FullPass 要求 `oracle_conditioned_success`（读到并采用正确版本），碰巧同时过 v1/v2 不算干净成功",
        "- 不得与 04a 正控或 WorkDiag v0.3 混排",
        "",
        "## 覆盖与主结果",
        "",
        f"- requested：{payload['summary']['requested']}",
        f"- measurement_valid：{payload['summary']['measurement_valid']}",
        f"- coverage：{payload['summary']['coverage']}",
        f"- oracle_conditioned FullPass Rate：{payload['summary']['full_pass_rate']}",
        f"- target_correct Rate：{payload['target_correct_rate']}",
        "",
        "### 分格",
        "",
        f"- Focused control：{payload['rates']['focused_control']}",
        f"- Focused intervention：{payload['rates']['focused_intervention']}",
        f"- Pipeline control：{payload['rates']['pipeline_control']}",
        f"- Pipeline intervention：{payload['rates']['pipeline_intervention']}",
        "",
        "## 决策",
        "",
        payload["decision"],
        "",
        "| task | variant | seed | Focused | Pipeline | EPG | focused first_error | pipeline first_error | focused in/art | pipeline in/art |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["pair_rows"]:
        lines.append(
            "| {task_id} | {variant} | {seed} | {focused} | {pipeline} | {epg} | {focused_first_error} | {pipeline_first_error} | {focused_input}/{focused_artifact} | {pipeline_input}/{pipeline_artifact} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## 逐格",
            "",
            "| instance | valid | FullPass | target_correct | oracle_conditioned | first_error |",
            "|---|---|---|---|---|---|",
        ]
    )
    for cell in payload["summary"]["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            "| {instance_id} | {measurement_valid} | {full_pass} | {target_correct} | {oracle_conditioned} | {first_error} |".format(
                instance_id=cell.get("instance_id"),
                measurement_valid=cell.get("measurement_valid"),
                full_pass=cell.get("full_pass"),
                target_correct=extra.get("target_correct"),
                oracle_conditioned=extra.get("oracle_conditioned_success"),
                first_error=(cell.get("process_profile") or {}).get("first_error"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    _pin_glm()
    out = BRIDGE_ROOT / "output" / "exp_gm_04b_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells: list[dict] = []
    for task in TASKS:
        for variant in VARIANTS:
            for track in TRACKS:
                for seed in SEEDS:
                    print(f"run {task['id']} variant={variant} track={track} seed={seed}", flush=True)
                    cell = _score_cell(task, variant, track, seed, out)
                    cells.append(cell)
                    extra = cell.get("extra") or {}
                    print(
                        f"  full_pass={cell.get('full_pass')} "
                        f"target_correct={extra.get('target_correct')} "
                        f"oracle_conditioned={extra.get('oracle_conditioned_success')} "
                        f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                        flush=True,
                    )
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    scored = [c for c in cells if c.get("full_pass") is not None]
    target_rate = (
        round(sum(int(bool((c.get("extra") or {}).get("target_correct"))) for c in scored) / len(scored), 4)
        if scored
        else None
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-04b",
        "task_id": "TASK-W1-revision",
        "status": "pilot",
        "ranking_eligible": False,
        "summary": summary,
        "target_correct_rate": target_rate,
        "rates": {
            "focused_control": _group_rates(cells, "focused", "control"),
            "focused_intervention": _group_rates(cells, "focused", "intervention"),
            "pipeline_control": _group_rates(cells, "pipeline", "control"),
            "pipeline_intervention": _group_rates(cells, "pipeline", "intervention"),
        },
        "pair_rows": _pair_rows(cells),
        "decision": "",
    }
    payload["decision"] = _decision(payload)
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = _render(payload)
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
