#!/usr/bin/env python3
"""EXP-GM-05 equal-budget multi-agent value. Freeze after Rule; then repeat 0."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_04c.roles import parse_review_json
from exp_gm_05.aggregate import summarize
from exp_gm_05.budget import MAX_TOKENS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_05.drop_loop import run_drop_cell
from exp_gm_05.multi_loop import run_multi_cell
from exp_gm_05.roles import executor_prompt, reviewer_prompt, rule_executor, rule_reviewer, self_check_prompt
from exp_gm_05.scoring import score_cell
from exp_gm_05.single_loop import run_single_cell
from exp_gm_05.tasks import TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths

WORKFLOW_ID = "exp_gm_05_equal_budget"
TRACKS = ("single", "multi", "drop")
VARIANTS = ("control", "intervention")
EXECUTOR_ID = 5
REVIEWER_ID = 6


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault(PROVIDER, {})
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
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _llm_executor(out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.schemas import WorkBrief

    n = {"i": 0}

    def _fn(brief: str, source: str | None, review):
        n["i"] += 1
        text = executor_prompt(brief, source, review)
        work = WorkBrief(
            task_id=f"exec_{n['i']}",
            agent_id=EXECUTOR_ID,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="编写 Python 脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=text,
            estimated_minutes=15,
            submitted_at=time.time(),
        )
        ctx = AdapterContext(artifacts_root=str(out_dir / "adapter_calls"), llm=_llm, config={})
        result = CodeAdapter().run(work, ctx)
        paths = result.artifact_paths or []
        if not paths or not os.path.isfile(paths[0]):
            return ""
        return Path(paths[0]).read_text(encoding="utf-8")

    return _fn


def _llm_reviewer(track: str):
    def _fn(draft: str, private: dict):
        prompt = self_check_prompt(draft, private) if track == "single" else reviewer_prompt(draft, private)
        try:
            return parse_review_json(_llm(prompt))
        except (ValueError, json.JSONDecodeError):
            return {}

    return _fn


def _rule_fns(task: dict):
    def executor(brief: str, source: str | None, review):
        return rule_executor(task, version="v1", review=review, current=source)

    def reviewer(draft: str, private: dict):
        return rule_reviewer(draft, task, private)

    return executor, reviewer


def _run_one(task, variant, track, repeat_id, out_root: Path, mode: str) -> dict:
    instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    runners = {"single": run_single_cell, "multi": run_multi_cell, "drop": run_drop_cell}
    if mode == "rule":
        executor_fn, reviewer_fn = _rule_fns(task)
    else:
        executor_fn = _llm_executor(run_dir)
        reviewer_fn = _llm_reviewer(track)
    loop = runners[track](
        task=task,
        variant=variant,
        task_id=instance_id,
        out_dir=run_dir,
        executor_fn=executor_fn,
        reviewer_fn=reviewer_fn,
    )
    return score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=repeat_id,
        loop=loop,
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
    )


def _write_report(cells: list[dict], out: Path, *, phase: str) -> dict:
    summary = summarize(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-05",
        "construct": "equal_budget_multi_agent_value",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "phase": phase,
        "ranking_eligible": False,
        "summary": summary,
        "cells": [
            {
                "instance_id": c.get("instance_id"),
                "measurement_valid": c.get("measurement_valid"),
                "full_pass": c.get("full_pass"),
                **(c.get("extra") or {}),
            }
            for c in cells
        ],
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# EXP-GM-05 Equal-budget multi-agent value",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- 阶段：{phase}",
        f"- 模型：{MODEL} temperature={TEMPERATURE} 每格 3 次调用",
        "- ranking_eligible：false",
        "- 不使用 typed-patch，不使用 04e 开发题或原留出题",
        "",
        "## 主结果",
        "",
        f"- requested：{summary['requested']}",
        f"- measurement_valid：{summary['measurement_valid']} coverage={summary['coverage']}",
        f"- MultiAgentNetBenefit：{summary['multi_agent_net_benefit']}",
        f"- ReviewCausalValue：{summary['review_causal_value']}",
        f"- VerifiedPatchAdoptionRate：{summary['verified_patch_adoption_rate']}",
        f"- repeat0_gate：{summary['repeat0_gate']}",
        "",
        "## 格",
        "",
        "| instance | track | variant | valid | FullPass | first_error |",
        "|---|---|---|---|---|---|",
    ]
    for cell in cells:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('track')} | {extra.get('variant')} | "
            f"{cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells = []
    for task in TASKS:
        for variant in VARIANTS:
            for track in TRACKS:
                print(f"run {task['id']} {variant} {track} repeat={repeat_id}", flush=True)
                cell = _run_one(task, variant, track, repeat_id, out, mode)
                extra = cell.get("extra") or {}
                print(
                    f"  valid={cell.get('measurement_valid')} full={cell.get('full_pass')} "
                    f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
                cells.append(cell)
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat-id", type=int, default=0)
    parser.add_argument("--mode", default="llm", choices=["llm", "rule"])
    parser.add_argument("--fill-repeats", action="store_true", help="after repeat 0 gate D, run 1 and 2")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", PROVIDER)
    if args.mode == "llm":
        _pin_glm()
        from config import CONFIG
        from gaworld.eval_mode import apply_eval_mode_runtime

        CONFIG.setdefault("eval_mode", {})["enabled"] = True
        apply_eval_mode_runtime(CONFIG)
    out = BRIDGE_ROOT / "output" / "exp_gm_05_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells = run_repeat(out, args.repeat_id, mode=args.mode)
    payload = _write_report(cells, out, phase=f"repeat_{args.repeat_id}")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    gate = payload["summary"]["repeat0_gate"]
    if args.repeat_id == 0 and args.fill_repeats and gate == "D_difference" and args.mode == "llm":
        for rid in (1, 2):
            cells.extend(run_repeat(out, rid, mode=args.mode))
        payload = _write_report(cells, out, phase="repeats_0_1_2")
        print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
