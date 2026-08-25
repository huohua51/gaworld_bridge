#!/usr/bin/env python3
"""Phase 2: fixed v1 draft, 18-cell review stage. 2 calls per cell."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_04c.roles import parse_review_json
from exp_gm_05b.aggregate import na_if_floor, paired_mean, rate, review_gate
from exp_gm_05b.budget import MAX_TOKENS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_05b.review_loop import run_review_cell
from exp_gm_05b.roles import executor_prompt, reviewer_prompt, rule_executor, rule_reviewer, self_check_prompt
from exp_gm_05b.scoring import score_cell
from exp_gm_05b.tasks import TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths

WORKFLOW_ID = "exp_gm_05b_review_stage"


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


def _llm_executor(out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.schemas import WorkBrief

    n = {"i": 0}

    def _fn(brief: str, source: str, review):
        n["i"] += 1
        work = WorkBrief(
            task_id=f"rew_{n['i']}",
            agent_id=5,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="编写 Python 脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=executor_prompt(brief, source, review),
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
        try:
            return parse_review_json(_llm(prompt))
        except (ValueError, json.JSONDecodeError):
            return {}

    return _fn


def _cell_row(cell: dict) -> dict:
    extra = cell.get("extra") or {}
    return {"instance_id": cell.get("instance_id"), "full_pass": cell.get("full_pass"), **extra}


def write_review_report(out: Path, cells: list[dict], *, repeats: list[int]) -> dict:
    gate = review_gate(cells)
    floor = gate in {"still_floor", "A_r0"}
    raw_review = paired_mean(cells, "multi", "single")
    raw_delivery = paired_mean(cells, "multi", "drop")
    delivered_adoption = rate(cells, "verified_patch_adoption", variant="intervention", track="multi")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-05b",
        "phase": "fixed_draft_review",
        "ranking_eligible": False,
        "repeats": repeats,
        "n_cells": len(cells),
        "gate": gate,
        "raw_review_stage_multi_agent_benefit": raw_review,
        "raw_review_delivery_value": raw_delivery,
        "estimands": {
            "review_stage_multi_agent_benefit": {"value": na_if_floor(raw_review, floor), "reason": gate},
            "review_delivery_value": {"value": na_if_floor(raw_delivery, floor), "reason": gate},
        },
        "false_positive_revision_rate": None
        if rate(cells, "review_decision_correct", variant="control") is None
        else round(1 - (rate(cells, "review_decision_correct", variant="control") or 0), 4),
        "true_revision_rate": rate(cells, "review_decision_correct", variant="intervention"),
        "verified_patch_adoption_rate": rate(cells, "verified_patch_adoption", variant="intervention"),
        "verified_patch_adoption_rate_multi_intervention": delivered_adoption,
        "fill_repeats": gate in {"review_has_value_fill_repeats", "independent_reviewer_value"},
        "open_04f": gate == "multi_negative_maybe_04f",
        "open_05c": gate in {"review_has_value_fill_repeats", "independent_reviewer_value"} and len(repeats) >= 3,
    }
    (out / "cell_table.json").write_text(
        json.dumps({**payload, "cells": [_cell_row(c) for c in cells]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# EXP-GM-05b Fixed-draft review stage",
        "",
        f"- repeats：{repeats}，n={len(cells)}",
        f"- 门：{gate}",
        f"- ReviewStageMultiAgentBenefit：{payload['estimands']['review_stage_multi_agent_benefit']['value']}",
        f"- ReviewDeliveryValue：{payload['estimands']['review_delivery_value']['value']}",
        f"- FalsePositiveRevisionRate：{payload['false_positive_revision_rate']}",
        f"- TrueRevisionRate：{payload['true_revision_rate']}",
        f"- VerifiedPatchAdoptionRate（含 Drop）：{payload['verified_patch_adoption_rate']}",
        f"- VerifiedPatchAdoptionRate（Multi 干预）：{payload['verified_patch_adoption_rate_multi_intervention']}",
        f"- 补重复：{payload['fill_repeats']}；开 04f：{payload['open_04f']}；开 05c：{payload['open_05c']}",
        "",
        "| instance | track | variant | valid | FullPass | first_error |",
        "|---|---|---|---|---|---|",
    ]
    for cell in cells:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('track')} | {extra.get('variant')} | "
            f"{cell.get('measurement_valid')} | {cell.get('full_pass')} | {extra.get('first_error')} |"
        )
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
    out = BRIDGE_ROOT / "output" / "exp_gm_05b_review_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells = []
    for task in TASKS:
        for variant in ("control", "intervention"):
            for track, drop in (("single", False), ("multi", False), ("drop", True)):
                instance = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                run_dir = out / "runs" / instance
                print(f"run {instance}", flush=True)
                loop = run_review_cell(
                    task=task, variant=variant, track=track, task_id=instance, out_dir=run_dir,
                    executor_fn=_llm_executor(run_dir), reviewer_fn=_llm_reviewer(track), drop=drop,
                )
                cell = score_cell(
                    task=task, variant=variant, track=track, repeat_id=repeat_id,
                    loop=loop, workflow_id=WORKFLOW_ID, instance_id=instance,
                )
                extra = cell.get("extra") or {}
                print(
                    f"  valid={cell.get('measurement_valid')} full={cell.get('full_pass')} "
                    f"err={extra.get('first_error')}",
                    flush=True,
                )
                cells.append(cell)
    (out / f"cell_table_r{repeat_id}.json").write_text(
        json.dumps({"repeat_id": repeat_id, "cells": [_cell_row(c) for c in cells]}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    merged: list[dict] = []
    repeats: list[int] = []
    for path in sorted(out.glob("cell_table_r*.json")):
        blob = json.loads(path.read_text(encoding="utf-8"))
        repeats.append(int(blob.get("repeat_id", path.stem.rsplit("r", 1)[-1])))
        for row in blob.get("cells") or []:
            merged.append({"instance_id": row.get("instance_id"), "full_pass": row.get("full_pass"), "measurement_valid": row.get("measurement_valid"), "extra": row})
    payload = write_review_report(out, merged, repeats=sorted(set(repeats)))
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    print(json.dumps({k: payload[k] for k in ("gate", "n_cells", "fill_repeats", "open_04f")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
