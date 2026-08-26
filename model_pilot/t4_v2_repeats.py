"""Run preregistered T4-v2 full-track repeats 1/2 against seed 0."""

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
from exp_gm_t4_02.loader import VARIANTS, load_tasks
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.t4_v2 import run_cell
from model_pilot.t4_v2_run import _eval_evidence
from model_pilot.t4_v2_scorer import SCORER_VERSION, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

REGISTRATION_PATH = (
    Path(__file__).with_name("registrations")
    / "T4_REGISTERED_TRANSPORT_GLM52_REPEATS_v1.yaml"
)
TASK_IDS = (
    "t4v2_reservoir_quality_001",
    "t4v2_substation_load_001",
    "t4v2_school_air_001",
)
REPEAT_IDS = (1, 2)
TRACK = "full"
MAX_CALLS = 48
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
    design = payload.get("design") or {}
    if tuple(design.get("task_ids") or ()) != TASK_IDS:
        errors.append("registered_task_order_mismatch")
    if tuple(design.get("variants") or ()) != VARIANTS:
        errors.append("registered_variant_order_mismatch")
    if tuple(design.get("repeat_ids") or ()) != REPEAT_IDS:
        errors.append("registered_repeat_order_mismatch")
    if str(design.get("track") or "") != TRACK:
        errors.append("registered_track_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("registered_call_budget_mismatch")
    if str(design.get("scorer_version") or "") != SCORER_VERSION:
        errors.append("registered_scorer_version_mismatch")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _observation(run_dir: Path, seed: int) -> dict[str, Any]:
    model_rows = _rows(run_dir / "model_trace.jsonl")
    requests = [row for row in model_rows if row.get("event") == "model_request"]
    responses = [row for row in model_rows if row.get("event") == "model_response"]
    source_request = requests[0] if requests else {}
    source_response = next(
        (
            row
            for row in responses
            if row.get("call_id") == source_request.get("call_id")
        ),
        {},
    )
    cell = json.loads((run_dir / "cell_result.json").read_text(encoding="utf-8"))
    criteria = {item["criterion_id"]: item for item in cell.get("criteria") or []}
    contract = next(
        (
            gate
            for gate in cell.get("gates") or []
            if gate.get("gate_id") == "model_responses_structured"
        ),
        {},
    )
    forward = (source_response.get("parsed") or {}).get("forward")
    if source_response.get("ok") is not True or not isinstance(forward, bool):
        forward = None
    return {
        "seed": seed,
        "source_forward": forward,
        "source_prompt_sha256": str(source_request.get("prompt_sha256") or ""),
        "complete_path": bool(
            (criteria.get("complete_propagation_path") or {}).get("passed")
        ),
        "target_accepted": bool(
            (criteria.get("target_update_accepted") or {}).get("passed")
        ),
        "model_contract_pass": bool(contract.get("passed")),
        "measurement_valid": bool(cell.get("measurement_valid")),
        "full_pass": cell.get("full_pass"),
        "first_error": str((cell.get("process_profile") or {}).get("first_error")),
        "model_calls": len(requests),
        "run_dir": str(run_dir),
    }


def _rate(values: list[bool]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def run_registered(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
) -> dict[str, Any]:
    """Execute 12 new cells and compare them with six frozen seed-0 cells."""
    registration, registration_sha256 = _registration()
    provider = registration.get("provider") or {}
    if client.info.live:
        if client.info.provider != str(provider.get("name")):
            raise ValueError("live provider does not match preregistration")
        if client.info.model_version != str(provider.get("model")):
            raise ValueError("live model does not match preregistration")

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    reference_root = BRIDGE_ROOT / str(
        (registration.get("design") or {})["reference_result_dir"]
    )
    tasks = {str(task["id"]): task for task in load_tasks()}
    budget = ModelCallBudget(MAX_CALLS, max_response_chars=2_000)
    evidence = _eval_evidence()
    observations: dict[tuple[str, str], list[dict[str, Any]]] = {}
    new_cells: list[dict[str, Any]] = []

    for task_id in TASK_IDS:
        for variant in VARIANTS:
            reference_run = (
                reference_root
                / "runs"
                / f"model_v2_{task_id}_{variant}_{TRACK}_s0"
            )
            observations[(task_id, variant)] = [_observation(reference_run, 0)]

    for task_id in TASK_IDS:
        task = tasks[task_id]
        for variant in VARIANTS:
            for repeat_id in REPEAT_IDS:
                run_id = f"model_v2_{task_id}_{variant}_{TRACK}_s{repeat_id}"
                run_dir = out / "runs" / run_id
                before = int(budget.snapshot()["calls_used"])
                runner = RecordedModelRunner(
                    run_dir / "model_trace.jsonl",
                    client,
                    budget,
                    temperature=TEMPERATURE,
                    allow_live_model=allow_live_model,
                    run_id=run_id,
                )
                loop = run_cell(task, variant, TRACK, run_dir, runner)
                cell = score_cell(
                    task=task,
                    variant=variant,
                    track=TRACK,
                    seed=repeat_id,
                    loop=loop,
                    eval_mode_evidence=evidence,
                )
                cell_path = run_dir / "cell_result.json"
                cell_path.write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                observation = _observation(run_dir, repeat_id)
                observation["new_model_calls"] = (
                    int(budget.snapshot()["calls_used"]) - before
                )
                observations[(task_id, variant)].append(observation)
                new_cells.append(
                    {"task_id": task_id, "variant": variant, **observation}
                )

    by_task_variant: dict[str, dict[str, Any]] = {}
    for task_id in TASK_IDS:
        for variant in VARIANTS:
            values = observations[(task_id, variant)]
            key = f"{task_id}:{variant}"
            prompt_hashes = sorted(
                {str(item["source_prompt_sha256"]) for item in values}
            )
            by_task_variant[key] = {
                "seeds": [int(item["seed"]) for item in values],
                "source_forward": [item["source_forward"] for item in values],
                "source_forward_exact_agreement": len(
                    {item["source_forward"] for item in values}
                )
                == 1,
                "source_forward_rate": _rate(
                    [item["source_forward"] is True for item in values]
                ),
                "complete_path_rate": _rate(
                    [bool(item["complete_path"]) for item in values]
                ),
                "target_acceptance_rate": _rate(
                    [bool(item["target_accepted"]) for item in values]
                ),
                "full_pass_rate": _rate(
                    [item["full_pass"] == 1 for item in values]
                ),
                "model_contract_rate": _rate(
                    [bool(item["model_contract_pass"]) for item in values]
                ),
                "source_prompt_sha256": prompt_hashes,
                "prompt_stable_across_seed0_1_2": len(prompt_hashes) == 1,
            }

    all_observations = [
        item for values in observations.values() for item in values
    ]
    first_errors = Counter(item["first_error"] for item in new_cells)
    all_pass = all(
        item["source_forward"] is True
        and item["complete_path"]
        and item["target_accepted"]
        and item["model_contract_pass"]
        and item["measurement_valid"]
        and item["full_pass"] == 1
        for item in all_observations
    )
    design_adherent = (
        len(new_cells) == 12
        and int(budget.snapshot()["calls_used"]) == MAX_CALLS
        and all(
            item["prompt_stable_across_seed0_1_2"]
            for item in by_task_variant.values()
        )
    )
    summary = {
        "pilot_id": registration["preregistration_id"],
        "registration_path": str(REGISTRATION_PATH),
        "registration_sha256": registration_sha256,
        "base_commit": registration["base_commit"],
        "reference_result_dir": str(reference_root),
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "live_model_explicitly_allowed": allow_live_model,
        "temperature": TEMPERATURE,
        "thinking": THINKING,
        "max_tokens_per_call": MAX_TOKENS,
        "ranking_eligible": False,
        "registered_design_adherent": design_adherent,
        "all_registered_outcomes_pass": all_pass,
        "new_cells": len(new_cells),
        "combined_cells": len(all_observations),
        "by_task_variant": by_task_variant,
        "pooled_seed0_1_2": {
            "source_forward_rate": _rate(
                [item["source_forward"] is True for item in all_observations]
            ),
            "complete_path_rate": _rate(
                [bool(item["complete_path"]) for item in all_observations]
            ),
            "target_acceptance_rate": _rate(
                [bool(item["target_accepted"]) for item in all_observations]
            ),
            "full_pass_rate": _rate(
                [item["full_pass"] == 1 for item in all_observations]
            ),
            "model_contract_rate": _rate(
                [bool(item["model_contract_pass"]) for item in all_observations]
            ),
            "new_first_error_counts": dict(sorted(first_errors.items())),
        },
        "budget": budget.snapshot(),
        "cells": new_cells,
    }
    if not client.info.live:
        summary["gate"] = (
            "offline_repeat_calibration_pass"
            if design_adherent and all_pass
            else "offline_repeat_calibration_failed"
        )
    else:
        summary["gate"] = "registered_repeat_pilot_recorded"
    (out / "REPEAT_MANIFEST.yaml").write_text(
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
        default=BRIDGE_ROOT / "output" / "model_pilot_t4_v2_repeats_v1",
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
        registration, _ = _registration()
        provider = registration.get("provider") or {}
        if args.provider != str(provider.get("name")):
            parser.error("registered live run requires provider paratera_glm")
        os.environ["GAWORLD_LLM_MODEL"] = str(provider["model"])
        os.environ["GAWORLD_LLM_THINKING"] = THINKING
        os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
        ensure_import_paths()
        client = GAWorldModelClient(
            args.provider,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        if client.info.model_version != str(provider["model"]):
            parser.error("registered live run requires model GLM-5.2")
        allow_live_model = True
    summary = run_registered(
        args.out,
        client,
        allow_live_model=allow_live_model,
    )
    print(yaml.safe_dump(summary, allow_unicode=True, sort_keys=False))
    return 0 if summary.get("gate") != "offline_repeat_calibration_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
