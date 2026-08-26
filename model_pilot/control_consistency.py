"""Run the preregistered T4 control/full decision-consistency pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from exp_gm_t4_01.loader import load_tasks
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.run import _eval_evidence
from model_pilot.t4 import run_cell
from model_pilot.t4_scorer import SCORER_VERSION, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

REGISTRATION_PATH = (
    Path(__file__).with_name("registrations")
    / "T4_CONTROL_CONSISTENCY_GLM52_v1.yaml"
)
TASK_IDS = (
    "t4_ferry_closure_001",
    "t4_clinic_recall_001",
    "t4_shelter_capacity_001",
)
REPLICATE_IDS = (0, 1, 2)
MAX_CALLS = 36
MAX_TOKENS = 256
TEMPERATURE = 0.0
THINKING = "disabled"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registration() -> tuple[dict[str, Any], str]:
    payload = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    for relative, expected in (payload.get("frozen_inputs") or {}).items():
        path = BRIDGE_ROOT / str(relative)
        if not path.is_file():
            errors.append(f"missing:{relative}")
            continue
        actual = _sha256(path)
        if actual != str(expected):
            errors.append(f"sha256_mismatch:{relative}:{actual}")
    if errors:
        raise RuntimeError("preregistration input validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _source_decision(path: Path) -> tuple[bool | None, str, str]:
    rows = _rows(path)
    requests = [row for row in rows if row.get("event") == "model_request"]
    if not requests:
        return None, "model_request_missing", ""
    source_request = requests[0]
    source_response = next(
        (
            row
            for row in rows
            if row.get("event") == "model_response"
            and row.get("call_id") == source_request.get("call_id")
        ),
        None,
    )
    if source_response is None:
        return None, "model_response_missing", str(source_request.get("prompt_sha256") or "")
    parsed = source_response.get("parsed") or {}
    decision = parsed.get("forward")
    if not source_response.get("ok") or not isinstance(decision, bool):
        decision = None
    return (
        decision,
        str(parsed.get("reason") or ",".join(source_response.get("errors") or [])),
        str(source_request.get("prompt_sha256") or ""),
    )


def _rate(values: list[bool]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def run_registered(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
) -> dict[str, Any]:
    """Execute exactly the nine cells fixed in the preregistration."""
    registration, registration_sha256 = _registration()
    design = registration.get("design") or {}
    if tuple(design.get("task_ids") or ()) != TASK_IDS:
        raise RuntimeError("registered task order does not match runner")
    if tuple(design.get("replicate_ids") or ()) != REPLICATE_IDS:
        raise RuntimeError("registered replicate order does not match runner")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        raise RuntimeError("registered call budget does not match runner")
    if str(design.get("scorer_version")) != SCORER_VERSION:
        raise RuntimeError("registered scorer version does not match runner")

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = {str(task["id"]): task for task in load_tasks()}
    budget = ModelCallBudget(MAX_CALLS, max_response_chars=2_000)
    eval_evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []

    for task_id in TASK_IDS:
        task = tasks[task_id]
        for replicate_id in REPLICATE_IDS:
            run_id = f"model_{task_id}_control_full_s{replicate_id}"
            run_dir = out / "runs" / run_id
            before = budget.snapshot()["calls_used"]
            runner = RecordedModelRunner(
                run_dir / "model_trace.jsonl",
                client,
                budget,
                temperature=TEMPERATURE,
                allow_live_model=allow_live_model,
                run_id=run_id,
            )
            loop = run_cell(task, "control", "full", run_dir, runner)
            cell = score_cell(
                task=task,
                variant="control",
                track="full",
                seed=replicate_id,
                loop=loop,
                eval_mode_evidence=eval_evidence,
            )
            cell_path = run_dir / "cell_result.json"
            cell_path.write_text(
                json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            source_forward, source_reason, source_prompt_sha256 = _source_decision(
                run_dir / "model_trace.jsonl"
            )
            path_criterion = next(
                item
                for item in cell["criteria"]
                if item["criterion_id"] == "complete_propagation_path"
            )
            contract_gate = next(
                item
                for item in cell["gates"]
                if item["gate_id"] == "model_responses_structured"
            )
            cells.append(
                {
                    "task_id": task_id,
                    "replicate_id": replicate_id,
                    "calls": budget.snapshot()["calls_used"] - before,
                    "source_forward": source_forward,
                    "source_reason": source_reason,
                    "source_prompt_sha256": source_prompt_sha256,
                    "complete_path": bool(path_criterion["passed"]),
                    "measurement_valid": bool(cell["measurement_valid"]),
                    "model_contract_pass": bool(contract_gate["passed"]),
                    "full_pass": cell["full_pass"],
                    "first_error": str(cell["process_profile"].get("first_error")),
                    "cell_result_path": str(cell_path),
                    "model_trace_path": str(run_dir / "model_trace.jsonl"),
                }
            )

    by_task: dict[str, dict[str, Any]] = {}
    for task_id in TASK_IDS:
        task_cells = [cell for cell in cells if cell["task_id"] == task_id]
        decisions = [cell["source_forward"] for cell in task_cells]
        true_count = sum(value is True for value in decisions)
        false_count = sum(value is False for value in decisions)
        prompt_hashes = sorted({cell["source_prompt_sha256"] for cell in task_cells})
        by_task[task_id] = {
            "source_decisions": decisions,
            "source_forward_rate": round(true_count / len(task_cells), 4),
            "source_forward_exact_agreement": (
                true_count == len(task_cells) or false_count == len(task_cells)
            ),
            "source_forward_consistency_rate": round(
                max(true_count, false_count) / len(task_cells), 4
            ),
            "complete_path_rate": _rate(
                [bool(cell["complete_path"]) for cell in task_cells]
            ),
            "full_pass_rate": _rate(
                [cell["full_pass"] == 1 for cell in task_cells]
            ),
            "source_prompt_sha256": prompt_hashes,
            "prompt_stable_across_replicates": len(prompt_hashes) == 1,
        }

    first_errors = Counter(cell["first_error"] for cell in cells)
    summary = {
        "pilot_id": registration["preregistration_id"],
        "registration_path": str(REGISTRATION_PATH),
        "registration_sha256": registration_sha256,
        "base_commit": registration["base_commit"],
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "live_model_explicitly_allowed": allow_live_model,
        "temperature": TEMPERATURE,
        "thinking": THINKING,
        "max_tokens_per_call": MAX_TOKENS,
        "ranking_eligible": False,
        "registered_design_adherent": (
            len(cells) == 9
            and all(item["measurement_valid"] for item in cells)
            and all(
                item["prompt_stable_across_replicates"]
                for item in by_task.values()
            )
        ),
        "n_cells": len(cells),
        "by_task": by_task,
        "pooled": {
            "source_forward_rate": _rate(
                [cell["source_forward"] is True for cell in cells]
            ),
            "complete_path_rate": _rate(
                [bool(cell["complete_path"]) for cell in cells]
            ),
            "full_pass_rate": _rate([cell["full_pass"] == 1 for cell in cells]),
            "model_contract_rate": _rate(
                [bool(cell["model_contract_pass"]) for cell in cells]
            ),
            "first_error_counts": dict(sorted(first_errors.items())),
        },
        "budget": budget.snapshot(),
        "cells": cells,
    }
    (out / "CONSISTENCY_MANIFEST.yaml").write_text(
        yaml.safe_dump(summary, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", help="Configured GAWorld provider name")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--fixture-oracle", action="store_true")
    parser.add_argument(
        "--out",
        type=Path,
        default=BRIDGE_ROOT / "output" / "model_pilot_t4_control_consistency_v1",
    )
    args = parser.parse_args()
    if args.fixture_oracle:
        if args.provider or args.allow_live_model:
            parser.error(
                "--fixture-oracle cannot be combined with live provider options"
            )
        client: ModelClient = oracle_fixture_client()
        allow_live_model = False
    else:
        if not args.allow_live_model:
            parser.error("live model execution requires --allow-live-model")
        if not args.provider:
            parser.error("live model execution requires --provider")
        os.environ["GAWORLD_LLM_MODEL"] = "GLM-5.2"
        os.environ["GAWORLD_LLM_THINKING"] = THINKING
        os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
        ensure_import_paths()
        client = GAWorldModelClient(
            args.provider,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        if client.info.model_version != "GLM-5.2":
            parser.error("registered live run requires model GLM-5.2")
        allow_live_model = True

    summary = run_registered(
        args.out,
        client,
        allow_live_model=allow_live_model,
    )
    print(yaml.safe_dump(summary, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
