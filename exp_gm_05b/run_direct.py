#!/usr/bin/env python3
"""Phase 1: 6-cell direct_final_spec. Gate on TargetCorrect before any review track."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_05b.aggregate import direct_gate, target_correct_count
from exp_gm_05b.budget import MAX_TOKENS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_05b.direct_loop import run_direct_cell
from exp_gm_05b.artifacts import render_source
from exp_gm_05b.scoring import score_cell
from exp_gm_05b.tasks import TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths

WORKFLOW_ID = "exp_gm_05b_direct_final_spec"


def _pin() -> None:
    ensure_import_paths()
    from config import CONFIG

    glm = CONFIG.setdefault("llm", {}).setdefault("providers", {}).setdefault(PROVIDER, {})
    if isinstance(glm, dict):
        glm["max_tokens"] = MAX_TOKENS
        glm["temperature"] = TEMPERATURE
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = PROVIDER
    tasks = dict(routing.get("tasks") or {})
    tasks["schedule"] = PROVIDER
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = PROVIDER


def _llm(prompt: str) -> str:
    _pin()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _executor(out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.schemas import WorkBrief

    n = {"i": 0}

    def _fn(brief: str) -> str:
        n["i"] += 1
        work = WorkBrief(
            task_id=f"direct_{n['i']}",
            agent_id=5,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="编写 Python 脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=brief + "\n只输出完整 Python 源码。\n",
            estimated_minutes=10,
            submitted_at=time.time(),
        )
        ctx = AdapterContext(artifacts_root=str(out_dir / "adapter_calls"), llm=_llm, config={})
        result = CodeAdapter().run(work, ctx)
        paths = result.artifact_paths or []
        if not paths or not os.path.isfile(paths[0]):
            return ""
        return Path(paths[0]).read_text(encoding="utf-8")

    return _fn


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    _pin()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    apply_eval_mode_runtime(CONFIG)
    out = BRIDGE_ROOT / "output" / "exp_gm_05b_direct_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells = []
    for task in TASKS:
        for variant in ("control", "intervention"):
            instance = f"{task['id']}_{variant}_direct_r0"
            run_dir = out / "runs" / instance
            print(f"run {instance}", flush=True)
            loop = run_direct_cell(
                task=task, variant=variant, task_id=instance, out_dir=run_dir, executor_fn=_executor(run_dir),
            )
            cell = score_cell(
                task=task, variant=variant, track="direct_final_spec", repeat_id=0,
                loop=loop, workflow_id=WORKFLOW_ID, instance_id=instance,
            )
            extra = cell.get("extra") or {}
            print(f"  valid={cell.get('measurement_valid')} target={extra.get('target_correct')} err={extra.get('first_error')}", flush=True)
            cells.append(cell)
    hits, n = target_correct_count(cells)
    gate = direct_gate(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-05b",
        "phase": "direct_final_spec",
        "ranking_eligible": False,
        "target_correct": f"{hits}/{n}",
        "gate": gate,
        "advance_to_review_stage": gate in {"intermediate_ok", "maybe_too_easy"},
        "cells": [{"instance_id": c.get("instance_id"), **(c.get("extra") or {})} for c in cells],
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# EXP-GM-05b Direct final spec",
        "",
        f"- TargetCorrect：{hits}/{n}",
        f"- 门：{gate}",
        f"- 进入固定初稿审核：{payload['advance_to_review_stage']}",
        "",
        "| instance | variant | target | first_error |",
        "|---|---|---|---|",
    ]
    for cell in cells:
        extra = cell.get("extra") or {}
        lines.append(f"| {cell.get('instance_id')} | {extra.get('variant')} | {extra.get('target_correct')} | {extra.get('first_error')} |")
    if payload["advance_to_review_stage"]:
        lines.append("\nDirect 过门。可以进入 18 格固定初稿审核。")
    else:
        lines.append("\nDirect 未过门。不进入多 Agent 比较。")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0 if payload["advance_to_review_stage"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
