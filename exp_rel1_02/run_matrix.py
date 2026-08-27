#!/usr/bin/env python3
"""Run the frozen REL1-v2 fixture or GLM-5.2 seed-0 matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.model_runner import (
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from exp_rel1_02.fixture import fixture_client
from exp_rel1_02.loader import TASK_IDS, VARIANTS, load_tasks
from exp_rel1_02.protocol import run_cell
from exp_rel1_02.scorer import SCORER_VERSION, WORKFLOW_ID, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

REGISTRATION_PATH = Path(__file__).with_name("registration.yaml")
MAX_CALLS = 30
MAX_TOKENS = 384
TEMPERATURE = 0.0


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registration() -> tuple[dict[str, Any], str]:
    body = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors = []
    for relative, expected in (body.get("frozen_inputs") or {}).items():
        path = (BRIDGE_ROOT / relative).resolve()
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif _sha(path) != expected:
            errors.append(f"sha256_mismatch:{relative}:{_sha(path)}")
    design = body.get("design") or {}
    if tuple(design.get("task_ids") or ()) != TASK_IDS:
        errors.append("task_order_mismatch")
    if tuple(design.get("variants") or ()) != VARIANTS:
        errors.append("variant_order_mismatch")
    if design.get("scorer_version") != SCORER_VERSION:
        errors.append("scorer_version_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("call_budget_mismatch")
    core_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(GAWORLD_ROOT), text=True).strip()
    if core_commit != body.get("required_gaworld_commit"):
        errors.append(f"gaworld_commit_mismatch:{core_commit}")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return body, _sha(REGISTRATION_PATH)


def _rate(cells: list[dict[str, Any]], field: str) -> float:
    valid = [cell for cell in cells if cell.get("measurement_valid")]
    if not valid:
        return 0.0
    if field == "full_pass":
        return round(sum(int(cell.get("full_pass") or 0) for cell in valid) / len(valid), 4)
    return round(sum(int(bool((cell.get("extra") or {}).get(field))) for cell in valid) / len(valid), 4)


def _gate(cells: list[dict[str, Any]], coverage: float) -> str:
    if len(cells) != 6 or coverage != 1.0:
        return "measurement_invalid"
    for field in (
        "formation_correct",
        "update_correct",
        "formation_action_bound",
        "update_action_bound",
    ):
        if _rate(cells, field) != 1.0:
            return f"{field}_failed"
    return "pass" if _rate(cells, "full_pass") == 1.0 else "regression_failed"


def run_matrix(out: Path, client: ModelClient, *, allow_live_model: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_hash = _registration()
    provider = registration["provider"]
    if client.info.live and (
        client.info.provider != provider["name"] or client.info.model_version != provider["model"]
    ):
        raise ValueError("live provider/model does not match preregistration")
    out.mkdir(parents=True, exist_ok=True)
    budget = ModelCallBudget(MAX_CALLS)
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            run_id = f"rel1_v2_{task['id']}_{variant}_full_s0"
            run_dir = out / "runs" / run_id
            print(f"run {run_id}", flush=True)
            runner = RecordedModelRunner(
                run_dir / "model_trace.jsonl",
                client,
                budget,
                temperature=TEMPERATURE,
                allow_live_model=allow_live_model,
                run_id=run_id,
            )
            loop = run_cell(task, variant, run_dir, runner)
            cell = score_cell(task, variant, loop)
            (run_dir / "cell_result.json").write_text(
                json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            cells.append(cell)
    workflow = summarize_workflow(WORKFLOW_ID, cells)
    gate = _gate(cells, workflow["coverage"])
    report = {
        "experiment_id": "EXP-GM-REL1-02",
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_hash,
        "phase": "model_seed0_regression" if client.info.live else "offline_fixture_calibration",
        "gate": gate,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "full_pass_rate": _rate(cells, "full_pass"),
        "formation_correct": _rate(cells, "formation_correct"),
        "update_correct": _rate(cells, "update_correct"),
        "formation_action_bound": _rate(cells, "formation_action_bound"),
        "update_action_bound": _rate(cells, "update_action_bound"),
        "first_error": dict(Counter((cell.get("process_profile") or {}).get("first_error") for cell in cells)),
        "budget": budget.snapshot(),
        "ap_rel1_01_closable": bool(client.info.live and gate == "pass"),
        "ap_rel1_02_closable": bool(client.info.live and gate == "pass"),
        "ap_rel1_03_closable": bool(client.info.live and gate == "pass"),
        "does_not_overwrite": ["EXP-GM-REL1"],
        "gaworld_commit": registration["required_gaworld_commit"],
    }
    (out / "cell_table.json").write_text(json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-oracle", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--out", type=Path, default=BRIDGE_ROOT / "output" / "exp_gm_rel1_02_20260827")
    args = parser.parse_args()
    if (args.max_calls, args.max_tokens, args.temperature) != (MAX_CALLS, MAX_TOKENS, TEMPERATURE):
        parser.error("registered run requires max_calls=30, max_tokens=384, temperature=0")
    if args.fixture_oracle:
        if args.provider or args.allow_live_model:
            parser.error("fixture mode cannot use live provider options")
        client: ModelClient = fixture_client()
    else:
        if not args.provider or not args.allow_live_model:
            parser.error("live run requires --provider and --allow-live-model")
        registration, _ = _registration()
        if args.provider != registration["provider"]["name"]:
            parser.error("provider does not match preregistration")
        os.environ["GAWORLD_LLM_MODEL"] = registration["provider"]["model"]
        os.environ["GAWORLD_LLM_THINKING"] = "disabled"
        os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
        ensure_import_paths()
        client = GAWorldModelClient(args.provider, temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
    _, report = run_matrix(args.out, client, allow_live_model=args.allow_live_model)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
