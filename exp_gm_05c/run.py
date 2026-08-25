#!/usr/bin/env python3
"""EXP-GM-05c repeat 0: shared v1 draft forked into Single / Multi / Drop."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_05c.aggregate import (
    common_first_error,
    na_if_extreme,
    paired_mean,
    repeat0_gate,
    track_table,
)
from exp_gm_05c.budget import MAX_TOKENS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_05c.contract import collect_review_action
from exp_gm_05c.fork_loop import generate_shared_draft, run_track_from_draft
from exp_gm_05c.roles import builder_draft_prompt, builder_revise_prompt, reviewer_prompt, self_check_prompt
from exp_gm_05c.scoring import score_cell
from exp_gm_05c.tasks import TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths

WORKFLOW_ID = "exp_gm_05c_r1_full_workflow"


def _pin() -> None:
    ensure_import_paths()
    from config import CONFIG

    glm = CONFIG.setdefault("llm", {}).setdefault("providers", {}).setdefault(PROVIDER, {})
    if isinstance(glm, dict):
        glm["max_tokens"] = MAX_TOKENS
        glm["temperature"] = TEMPERATURE
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = PROVIDER
    routing["tasks"] = {**(routing.get("tasks") or {}), "schedule": PROVIDER}
    os.environ["GAWORLD_LLM_PROVIDER"] = PROVIDER


def _llm(prompt: str) -> str:
    _pin()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _llm_generate(out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.schemas import WorkBrief

    n = {"i": 0}

    def _fn(brief: str) -> str:
        n["i"] += 1
        work = WorkBrief(
            task_id=f"draft_{n['i']}",
            agent_id=5,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="编写 Python 脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=builder_draft_prompt(brief),
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


def _llm_revise(out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.schemas import WorkBrief

    n = {"i": 0}

    def _fn(brief: str, source: str, review):
        n["i"] += 1
        work = WorkBrief(
            task_id=f"rev_{n['i']}",
            agent_id=5,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="编写 Python 脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=builder_revise_prompt(brief, source, review),
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


def _llm_reviewer(track: str):
    def _fn(draft: str, private: dict):
        prompt = self_check_prompt(draft, private) if track == "single" else reviewer_prompt(draft, private)
        return collect_review_action(_llm, prompt)

    return _fn


def write_report(out: Path, cells: list[dict], *, repeat_id: int) -> dict:
    gate = repeat0_gate(cells, rerun=True)
    outcome = paired_mean(cells, "multi", "single", "target")
    workflow = paired_mean(cells, "multi", "single", "full")
    delivery_t = paired_mean(cells, "multi", "drop", "target")
    delivery_f = paired_mean(cells, "multi", "drop", "full")
    table = track_table(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-05c-r1",
        "parent": "EXP-GM-05c-r0",
        "change_scope": "review_action_output_contract_only",
        "repeat_id": repeat_id,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "gate": gate,
        "raw": {
            "outcome_multi_agent_net_benefit": outcome,
            "workflow_multi_agent_net_benefit": workflow,
            "review_delivery_value_target": delivery_t,
            "review_delivery_value_full": delivery_f,
        },
        "estimands": {
            "outcome_multi_agent_net_benefit": {"value": na_if_extreme(outcome, gate), "reason": gate},
            "workflow_multi_agent_net_benefit": {"value": na_if_extreme(workflow, gate), "reason": gate},
            "review_delivery_value_target": {"value": na_if_extreme(delivery_t, gate), "reason": gate},
            "review_delivery_value_full": {"value": na_if_extreme(delivery_f, gate), "reason": gate},
        },
        "tracks": table,
        "common_first_error": common_first_error(cells),
        "fill_repeats": gate == "D_difference",
        "open_04f": False,
        "heldout": "not_created",
    }
    rows = []
    for cell in cells:
        extra = cell.get("extra") or {}
        rows.append({"instance_id": cell.get("instance_id"), "full_pass": cell.get("full_pass"), **extra})
    (out / "cell_table.json").write_text(json.dumps({**payload, "cells": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# EXP-GM-05c-r1 Equal-budget full workflow (repeat 0, review contract)",
        "",
        f"- 模型：{MODEL}，temperature={TEMPERATURE}",
        f"- ranking_eligible：false；n={len(cells)}",
        "- 共同 v1 初稿分叉；v2 在初稿生成后才发布",
        f"- 预注册门：{gate}",
        f"- OutcomeMultiAgentNetBenefit：{payload['estimands']['outcome_multi_agent_net_benefit']['value']}",
        f"- WorkflowMultiAgentNetBenefit：{payload['estimands']['workflow_multi_agent_net_benefit']['value']}",
        f"- ReviewDeliveryValue_target：{payload['estimands']['review_delivery_value_target']['value']}",
        f"- ReviewDeliveryValue_full：{payload['estimands']['review_delivery_value_full']['value']}",
        f"- 共同首错：{payload['common_first_error']}",
        "",
        "| 指标 | Single | Multi | Drop |",
        "| --- | ---: | ---: | ---: |",
    ]
    labels = [
        ("Coverage", "coverage"),
        ("TargetCorrect", "target_correct"),
        ("FullPass", "full_pass"),
        ("StrictPair", "strict_pair"),
        ("FalsePositiveRevisionRate", "false_positive_revision_rate"),
        ("VerifiedPatchAdoptionRate", "verified_patch_adoption_rate"),
    ]
    for label, key in labels:
        lines.append(
            f"| {label} | {table['single'][key]} | {table['multi'][key]} | {table['drop'][key]} |"
        )
    lines += [
        "",
        "| instance | track | variant | valid | TargetCorrect | FullPass | first_error | sha256 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cell in cells:
        extra = cell.get("extra") or {}
        sha = str(extra.get("shared_draft_sha256") or "")[:12]
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('track')} | {extra.get('variant')} | "
            f"{cell.get('measurement_valid')} | {extra.get('target_correct')} | {cell.get('full_pass')} | "
            f"{extra.get('first_error')} | {sha} |"
        )
    if gate == "A_r0_again":
        lines.append("\nCoverage 仍低于 100%。四个净价值 N/A。停止反复调提示，输出契约登记为平台缺口。")
    elif gate != "D_difference":
        lines.append("\nrepeat 0 未同时脱离地板和天花板，不补 repeat 1/2，不建留出题。")
    else:
        lines.append("\nrepeat 0 脱离地板和天花板。按预注册可补 54 格，本次只完成 18 格重跑。")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat-id", type=int, default=0)
    args = parser.parse_args()
    repeat_id = int(args.repeat_id)
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    _pin()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    apply_eval_mode_runtime(CONFIG)
    out = BRIDGE_ROOT / "output" / "exp_gm_05c_r1_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells = []
    for task in TASKS:
        for variant in ("control", "intervention"):
            shared_dir = out / "shared_drafts" / f"{task['id']}_{variant}_r{repeat_id}"
            print(f"draft {task['id']} {variant} r{repeat_id}", flush=True)
            shared = generate_shared_draft(
                task=task,
                variant=variant,
                repeat_id=repeat_id,
                out_dir=shared_dir,
                generate_fn=_llm_generate(shared_dir),
            )
            print(f"  sha={shared['sha256'][:12]} leak={shared['leak_on_first_brief']}", flush=True)
            for track, drop in (("single", False), ("multi", False), ("drop", True)):
                instance = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                run_dir = out / "runs" / instance
                print(f"run {instance}", flush=True)
                loop = run_track_from_draft(
                    task=task,
                    variant=variant,
                    track=track,
                    task_id=instance,
                    out_dir=run_dir,
                    shared=shared,
                    revise_fn=_llm_revise(run_dir),
                    reviewer_fn=_llm_reviewer(track),
                    drop=drop,
                )
                cell = score_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    repeat_id=repeat_id,
                    loop=loop,
                    workflow_id=WORKFLOW_ID,
                    instance_id=instance,
                )
                extra = cell.get("extra") or {}
                print(
                    f"  valid={cell.get('measurement_valid')} tc={extra.get('target_correct')} "
                    f"full={cell.get('full_pass')} err={extra.get('first_error')}",
                    flush=True,
                )
                cells.append(cell)
    payload = write_report(out, cells, repeat_id=repeat_id)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    print(json.dumps({"gate": payload["gate"], "fill_repeats": payload["fill_repeats"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
