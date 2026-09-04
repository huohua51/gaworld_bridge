#!/usr/bin/env python3
"""Run the preregistered C1-06 post-merge fresh-surface regression."""

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

from benchmark_core.model_runner_v2 import (
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from exp_gm_c1_06.fixture import fixture_client
from exp_gm_c1_06.loader import TASK_IDS, VARIANTS, load_tasks
from exp_gm_c1_06.protocol import PROMPT_PROTOCOL, run_cell
from exp_gm_c1_06.scorer import SCORER_VERSION, WORKFLOW_ID, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

REGISTRATION_PATH = Path(__file__).with_name("registration.yaml")
PROVIDER = "paratera_glm"
MODEL = "GLM-5.2"
BASE_URL = "https://llmapi.paratera.com/v1"
MAX_CALLS = 36
MAX_TOKENS = 384
TEMPERATURE = 0.0
THINKING = "disabled"
RESPONSE_FORMAT = {"type": "json_object"}
RETRY_ATTEMPTS = 1
JSON_NORMALIZATION = "strict"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registration() -> tuple[dict[str, Any], str]:
    body = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    for relative, expected in (body.get("frozen_inputs") or {}).items():
        path = (BRIDGE_ROOT / relative).resolve()
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif _sha(path) != str(expected):
            errors.append(f"sha256_mismatch:{relative}:{_sha(path)}")
    design = body.get("design") or {}
    settings = body.get("provider") or {}
    if tuple(design.get("task_ids") or ()) != TASK_IDS:
        errors.append("task_order_mismatch")
    if tuple(design.get("variants") or ()) != VARIANTS:
        errors.append("variant_order_mismatch")
    if design.get("scorer_version") != SCORER_VERSION:
        errors.append("scorer_version_mismatch")
    if design.get("prompt_protocol") != PROMPT_PROTOCOL:
        errors.append("prompt_protocol_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("call_budget_mismatch")
    expected_settings = {
        "name": PROVIDER,
        "model": MODEL,
        "base_url": BASE_URL,
        "temperature": TEMPERATURE,
        "thinking": THINKING,
        "max_tokens_per_call": MAX_TOKENS,
        "response_format": RESPONSE_FORMAT,
        "retry_attempts": RETRY_ATTEMPTS,
        "json_normalization": JSON_NORMALIZATION,
    }
    for key, expected in expected_settings.items():
        if settings.get(key) != expected:
            errors.append(f"provider_setting_mismatch:{key}")
    core_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(GAWORLD_ROOT), text=True
    ).strip()
    if core_commit != body.get("required_gaworld_commit"):
        errors.append(f"gaworld_commit_mismatch:{core_commit}")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return body, _sha(REGISTRATION_PATH)


def _rate(cells: list[dict[str, Any]], field: str, variant: str | None = None) -> float:
    subset = [
        cell for cell in cells
        if cell.get("measurement_valid")
        and (variant is None or (cell.get("extra") or {}).get("variant") == variant)
    ]
    if not subset:
        return 0.0
    if field == "full_pass":
        return round(sum(int(cell.get("full_pass") or 0) for cell in subset) / len(subset), 4)
    return round(sum(int(bool((cell.get("extra") or {}).get(field))) for cell in subset) / len(subset), 4)


def _gate(cells: list[dict[str, Any]], coverage: float) -> str:
    if len(cells) != 6 or coverage != 1.0:
        return "measurement_invalid"
    checks = (
        (_rate(cells, "priority_nack_path", "intervention"), 1.0, "priority_nack_missed"),
        (_rate(cells, "priority_nack_path", "control"), 0.0, "control_priority_nack"),
        (_rate(cells, "retry_recovery_success", "intervention"), 1.0, "retry_not_recovered"),
        (_rate(cells, "platform_identifier_ownership"), 1.0, "platform_binding_failed"),
        (_rate(cells, "spec_revision_advanced"), 1.0, "spec_revision_failed"),
        (_rate(cells, "stale_plan_rejected"), 1.0, "stale_plan_not_rejected"),
        (_rate(cells, "full_pass"), 1.0, "regression_failed"),
    )
    for actual, expected, failure in checks:
        if actual != expected:
            return failure
    return "pass"


def run_matrix(
    out: Path, client: ModelClient, *, allow_live_model: bool
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_hash = _registration()
    if client.info.live and (
        client.info.provider != PROVIDER or client.info.model_version != MODEL
    ):
        raise ValueError("live provider/model does not match preregistration")
    out.mkdir(parents=True, exist_ok=True)
    budget = ModelCallBudget(MAX_CALLS)
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for variant in VARIANTS:
            run_id = f"c1_v6_{task['id']}_{variant}_full_s0"
            run_dir = out / "runs" / run_id
            print(f"run {run_id}", flush=True)
            runner = RecordedModelRunner(
                run_dir / "model_trace.jsonl",
                client,
                budget,
                temperature=TEMPERATURE,
                allow_live_model=allow_live_model,
                run_id=run_id,
                json_normalization=JSON_NORMALIZATION,
            )
            loop = run_cell(task, variant, run_dir, runner)
            cell = score_cell(task, variant, loop)
            (run_dir / "cell_result.json").write_text(
                json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            cells.append(cell)
    workflow = summarize_workflow(WORKFLOW_ID, cells)
    gate = _gate(cells, workflow["coverage"])
    snapshot = budget.snapshot()
    if client.info.live and gate == "pass" and (
        snapshot["calls_used"] != MAX_CALLS
        or snapshot["transport_attempts_observed"] != MAX_CALLS
        or snapshot["transport_retries_observed"] != 0
    ):
        gate = "transport_audit_failed"
    report = {
        "experiment_id": "EXP-GM-C1-06",
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_hash,
        "phase": "postmerge_model_seed0_regression" if client.info.live else "offline_fixture_calibration",
        "gate": gate,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "full_pass_rate": _rate(cells, "full_pass"),
        "priority_nack_intervention": _rate(cells, "priority_nack_path", "intervention"),
        "priority_nack_control": _rate(cells, "priority_nack_path", "control"),
        "retry_recovery_intervention": _rate(cells, "retry_recovery_success", "intervention"),
        "platform_identifier_ownership": _rate(cells, "platform_identifier_ownership"),
        "spec_revision_advanced": _rate(cells, "spec_revision_advanced"),
        "stale_plan_rejected": _rate(cells, "stale_plan_rejected"),
        "first_error": dict(Counter((cell.get("process_profile") or {}).get("first_error") for cell in cells)),
        "budget": snapshot,
        "core_fix_commits_in_history": [
            "ad93e9d8c2848158bdf78ad789cb3b7c6a9d4d49",
        ],
        "gaworld_commit": registration["required_gaworld_commit"],
        "does_not_overwrite": ["EXP-GM-C1-02", "EXP-GM-C1-03", "EXP-GM-C1-04", "EXP-GM-C1-05"],
    }
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return cells, report


def _live_client() -> GAWorldModelClient:
    os.environ["GAWORLD_LLM_API_BASE"] = BASE_URL
    os.environ["GAWORLD_LLM_MODEL"] = MODEL
    os.environ["GAWORLD_LLM_THINKING"] = THINKING
    os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
    ensure_import_paths()
    return GAWorldModelClient(
        PROVIDER,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        response_format=RESPONSE_FORMAT,
        retry_attempts=RETRY_ATTEMPTS,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture-oracle", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.fixture_oracle:
        if args.provider or args.allow_live_model:
            parser.error("fixture mode cannot use live options")
        client: ModelClient = fixture_client()
        allow_live = False
    else:
        if args.provider != PROVIDER or not args.allow_live_model:
            parser.error("live mode requires --provider paratera_glm --allow-live-model")
        client = _live_client()
        allow_live = True
    _, report = run_matrix(args.out, client, allow_live_model=allow_live)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
