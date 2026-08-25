#!/usr/bin/env python3
"""EXP-GM-04a: TASK-W1-lite Focused vs work-pipeline Pilot.

3 tasks × 2 tracks × 3 repeats = 18 cells.
This is not multi-agent plan/review E2E. Ranking is off.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow
from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04.tasks import TASKS

WORKFLOW_ID = "exp_gm_04a_task_w1_lite"
SEEDS = [0, 1, 2]
TRACKS = ("focused", "e2e")
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


def _brief(task_id: str, brief_text: str, seed: int, track: str):
    from gaworld.work.schemas import WorkBrief

    return WorkBrief(
        task_id=f"{task_id}_{track}_s{seed}",
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
    )


def _run_focused(brief, out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter

    ctx = AdapterContext(artifacts_root=str(out_dir / "artifacts"), llm=_llm, config={})
    result = CodeAdapter().run(brief, ctx)
    events = ["adapter_run"]
    if result.artifact_paths:
        events.append("artifact_written")
    return result, events, "adapter"


def _run_e2e(brief, out_dir: Path, agent: dict):
    from gaworld.work.adapters.base import AdapterContext, make_failed
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.ingest import absorb_completed_for
    from gaworld.work.queue import WorkQueue
    from gaworld.work.worker import WorkerPool

    queue = WorkQueue(str(out_dir / "queue.jsonl"))
    artifacts_root = str(out_dir / "artifacts")

    def ctx_factory(_name: str) -> AdapterContext:
        return AdapterContext(artifacts_root=artifacts_root, llm=_llm, config={})

    worker = WorkerPool(
        queue=queue,
        adapters={"code": CodeAdapter()},
        ctx_factory=ctx_factory,
        max_workers=1,
        task_timeout_seconds=180,
        poll_interval=0.05,
    )
    events = ["queue_submit"]
    queue.submit(brief)
    executed = worker.drain_sync(max_iterations=8)
    queued = getattr(queue, "_results", {}).get(brief.task_id)
    if executed:
        events.extend(["queue_claim", "adapter_run", "queue_result"])
    absorbed = absorb_completed_for(
        agent, queue=queue, market=None, sim_day=1, sim_time="10:00", limit=5
    )
    if absorbed:
        events.append("absorb")
        return absorbed[0], events, "work_pipeline"
    if queued is not None:
        events.append("result_from_queue_not_absorbed")
        return queued, events, "work_pipeline"
    events.append("pipeline_empty")
    return make_failed(brief, "work_pipeline produced no result", time.time()), events, "work_pipeline"


def _score_cell(task: dict, track: str, seed: int, out_root: Path) -> dict:
    ensure_import_paths()
    from gaworld.eval_mode import apply_eval_mode_runtime
    from config import CONFIG

    cfg = CONFIG
    cfg.setdefault("eval_mode", {})
    cfg["eval_mode"]["enabled"] = True
    apply_eval_mode_runtime(cfg)

    instance_id = f"{task['id']}_{track}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    brief = _brief(task["id"], task["brief"], seed, track)
    agent = {
        "id": AGENT_ID,
        "name": "王思远",
        "job": "产品经理",
        "state": {"emotion": 0.6, "stress": 0.4, "econ_security": 0.5},
        "memory": [],
    }
    started = time.time()
    if track == "focused":
        result, events, producer = _run_focused(brief, run_dir)
    else:
        result, events, producer = _run_e2e(brief, run_dir, agent)
        # If absorb missed but queue has a result, recover path from queue file.
        if not result.artifact_paths:
            from gaworld.work.queue import WorkQueue

            q = WorkQueue(str(run_dir / "queue.jsonl"))
            queued = getattr(q, "_results", {}).get(brief.task_id)
            if queued is not None:
                result = queued
                events.append("result_from_queue_not_absorbed")
    elapsed = round(time.time() - started, 3)
    paths = list(result.artifact_paths or [])
    artifact = paths[0] if paths else None
    oracle = score_hidden_tests(artifact, task["oracle"])
    adapter_ok = result.status == "ok"
    exists = bool(artifact and os.path.isfile(artifact))
    n_tests = int(task["n_tests"])
    pass_rate = (oracle["pass_count"] / n_tests) if oracle["evaluable"] and n_tests else 0.0
    first_error = "none"
    if not exists:
        first_error = "no_artifact"
    elif not adapter_ok:
        first_error = "adapter_failed"
    elif not oracle["passed"]:
        first_error = oracle.get("first_error") or "oracle_tests_failed"
    elif track == "e2e" and "absorb" not in events:
        first_error = "absorb_missing"

    measurement = [
        GateResult("execution_valid", True, layer="R0", detail=f"track={track} elapsed={elapsed}s"),
        GateResult("eval_mode_on", True, layer="R0", detail="eval_mode.enabled"),
        GateResult("oracle_present", task["oracle"].is_file(), layer="R0", detail=str(task["oracle"])),
    ]
    artifact_gates = [
        GateResult("artifact_exists", exists and adapter_ok, layer="R1", detail=str(paths)),
        GateResult("producer_is_agent_adapter", producer in {"adapter", "work_pipeline"}, layer="R1"),
    ]
    agent_success = bool(oracle["passed"] and exists and adapter_ok)
    criteria = [
        CriterionResult(
            criterion_id="hidden_oracle_full_pass",
            layer="R2",
            scorer="pytest_hidden",
            evaluable=oracle["evaluable"],
            score=1.0 if oracle["passed"] else 0.0,
            passed=oracle["passed"],
            critical=True,
            evidence_ids=paths,
            detail=oracle.get("stdout_tail", "")[:400],
        ),
        CriterionResult(
            criterion_id="hidden_test_pass_rate",
            layer="R2",
            scorer="pytest_hidden",
            evaluable=oracle["evaluable"],
            score=round(pass_rate, 4),
            passed=oracle["passed"],
            critical=False,
            detail=f"{oracle['pass_count']}/{n_tests}",
        ),
    ]
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=measurement,
        artifact_gates=artifact_gates,
        criteria=criteria,
        process_profile={
            "first_error": first_error,
            "events": events,
            "producer": producer,
            "absorb_occurred": "absorb" in events,
        },
        extra={
            "task_id": task["id"],
            "track": track,
            "seed": seed,
            "run_id": instance_id,
            "model_version": "GLM-4-Flash",
            "temperature": 0,
            "mechanism_condition": track,
            "adapter_status": result.status,
            "adapter_error": result.error,
            "oracle": oracle,
            "elapsed_s": elapsed,
            "agent_success": agent_success,
            "system_success": agent_success,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(
        json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return cell


def _epg(cells: list[dict]) -> list[dict]:
    rows = []
    for task in TASKS:
        for seed in SEEDS:
            pair = {
                c["extra"]["track"]: c
                for c in cells
                if c.get("extra", {}).get("task_id") == task["id"] and c.get("extra", {}).get("seed") == seed
            }
            focused = pair.get("focused")
            e2e = pair.get("e2e")
            if not focused or not e2e:
                continue
            f_ok = int(focused.get("full_pass") or 0) if focused.get("measurement_valid") else None
            e_ok = int(e2e.get("full_pass") or 0) if e2e.get("measurement_valid") else None
            loss = None if f_ok is None or e_ok is None else f_ok - e_ok
            rows.append(
                {
                    "task_id": task["id"],
                    "seed": seed,
                    "focused": f_ok,
                    "e2e": e_ok,
                    "epg": loss,
                    "focused_first_error": (focused.get("process_profile") or {}).get("first_error"),
                    "e2e_first_error": (e2e.get("process_profile") or {}).get("first_error"),
                }
            )
    return rows


def _render(payload: dict) -> str:
    lines = [
        "# EXP-GM-04a TASK-W1-lite Pilot",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 状态：pilot，不可排名",
        "- 对照：Focused=`direct_adapter` vs E2E=`work_pipeline`（同一 brief）",
        "- 不是多 Agent 计划/审核工作流；不得与 WorkDiag v0.3 EPG 混排",
        "",
        "## 覆盖与主结果",
        "",
        f"- requested：{payload['summary']['requested']}",
        f"- measurement_valid：{payload['summary']['measurement_valid']}",
        f"- coverage：{payload['summary']['coverage']}",
        f"- FullPass Rate（全部 18 格混合）：{payload['summary']['full_pass_rate']}",
        "",
        "### 分轨",
        "",
        f"- Focused FullPass Rate：{payload['focused_rate']}",
        f"- E2E FullPass Rate：{payload['e2e_rate']}",
        f"- 流程传播损失 EPG：{payload['epg_macro']}",
        "",
        "| task | seed | Focused | E2E | EPG | focused first_error | e2e first_error |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["epg_rows"]:
        lines.append(
            "| {task_id} | {seed} | {focused} | {e2e} | {epg} | {focused_first_error} | {e2e_first_error} |".format(
                **row
            )
        )
    lines.extend(["", "## 逐格", "", "| instance | valid | FullPass | TaskScore | first_error |", "|---|---|---|---|---|"])
    for cell in payload["summary"]["cells"]:
        lines.append(
            "| {instance_id} | {measurement_valid} | {full_pass} | {task_score} | {first_error} |".format(
                instance_id=cell.get("instance_id"),
                measurement_valid=cell.get("measurement_valid"),
                full_pass=cell.get("full_pass"),
                task_score=cell.get("task_score"),
                first_error=(cell.get("process_profile") or {}).get("first_error"),
            )
        )
    lines.extend(
        [
            "",
            "## 可交给同学改的问题（本 Pilot）",
            "",
            "若 E2E 相对 Focused 掉分：优先查 WorkQueue claim/result/absorb 是否丢产物。",
            "若两轨都在 `oracle_import_failed`：CodeAdapter 没有产出约定函数名。",
            "若两轨都过：工作子系统对单 Agent 脚本不是瓶颈，完整 TASK-W1 仍缺审核/分工原语。",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    _pin_glm()
    out = BRIDGE_ROOT / "output" / "exp_gm_04a_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells: list[dict] = []
    for task in TASKS:
        for seed in SEEDS:
            for track in TRACKS:
                print(f"run {task['id']} track={track} seed={seed}", flush=True)
                cell = _score_cell(task, track, seed, out)
                cells.append(cell)
                print(
                    f"  full_pass={cell.get('full_pass')} first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    focused = [c for c in cells if c.get("extra", {}).get("track") == "focused" and c.get("full_pass") is not None]
    e2e = [c for c in cells if c.get("extra", {}).get("track") == "e2e" and c.get("full_pass") is not None]
    focused_rate = sum(int(c["full_pass"]) for c in focused) / len(focused) if focused else None
    e2e_rate = sum(int(c["full_pass"]) for c in e2e) / len(e2e) if e2e else None
    epg_macro = None if focused_rate is None or e2e_rate is None else round(focused_rate - e2e_rate, 4)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-04a",
        "task_id": "TASK-W1-lite",
        "status": "pilot",
        "ranking_eligible": False,
        "summary": summary,
        "focused_rate": None if focused_rate is None else round(focused_rate, 4),
        "e2e_rate": None if e2e_rate is None else round(e2e_rate, 4),
        "epg_macro": epg_macro,
        "epg_rows": _epg(cells),
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = _render(payload)
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
