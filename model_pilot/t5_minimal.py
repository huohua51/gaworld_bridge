"""Run the preregistered minimal T5 live causal-chain pilot."""

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
from exp_gm_t5_01.loader import CONDITIONS, load_tasks
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.run import _eval_evidence
from model_pilot.t5 import run_cell
from model_pilot.t5_scorer import SCORER_VERSION, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

REGISTRATION_PATH = (
    Path(__file__).with_name("registrations") / "T5_MINIMAL_CAUSAL_GLM52_v1.yaml"
)
TASK_ID = "t5_low_emission_zone"
TRACK = "full"
SEED = 0
MAX_CALLS = 12
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
    if str(design.get("task_id") or "") != TASK_ID:
        errors.append("registered_task_mismatch")
    if tuple(design.get("conditions") or ()) != CONDITIONS:
        errors.append("registered_condition_order_mismatch")
    if str(design.get("track") or "") != TRACK:
        errors.append("registered_track_mismatch")
    if int(design.get("seed", -1)) != SEED:
        errors.append("registered_seed_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("registered_call_budget_mismatch")
    if str(design.get("scorer_version") or "") != SCORER_VERSION:
        errors.append("registered_scorer_version_mismatch")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _rate(values: list[bool]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def run_registered(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
) -> dict[str, Any]:
    """Execute the fixed three-condition, one-task T5 matrix."""
    registration, registration_sha256 = _registration()
    provider = registration.get("provider") or {}
    if client.info.live:
        if client.info.provider != str(provider.get("name")):
            raise ValueError("live provider does not match preregistration")
        if client.info.model_version != str(provider.get("model")):
            raise ValueError("live model does not match preregistration")

    task = next(task for task in load_tasks() if str(task["id"]) == TASK_ID)
    target_groups = {str(group) for group in task["target_groups"]}
    target_agents = sorted(
        str(resident["agent_id"])
        for resident in task["residents"]
        if str(resident["group"]) in target_groups
    )
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    budget = ModelCallBudget(MAX_CALLS, max_response_chars=2_000)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []

    for condition in CONDITIONS:
        run_id = f"model_minimal_{TASK_ID}_{condition}_{TRACK}_s{SEED}"
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
        loop = run_cell(task, condition, TRACK, run_dir, runner)
        cell = score_cell(
            task=task,
            condition=condition,
            track=TRACK,
            seed=SEED,
            loop=loop,
            eval_mode_evidence=evidence,
        )
        cell_path = run_dir / "cell_result.json"
        cell_path.write_text(
            json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        contract = next(
            gate
            for gate in cell["gates"]
            if gate["gate_id"] == "model_responses_structured"
        )
        spillover = next(
            item
            for item in cell["criteria"]
            if item["criterion_id"] == "no_untargeted_spillover"
        )
        cells.append(
            {
                "condition": condition,
                "calls": int(budget.snapshot()["calls_used"]) - before,
                "measurement_valid": bool(cell["measurement_valid"]),
                "model_contract_pass": bool(contract["passed"]),
                "full_pass": cell["full_pass"],
                "first_error": str(cell["process_profile"].get("first_error")),
                "behavior_change_rate": float(
                    cell["extra"]["behavior_change_rate"]
                ),
                "changed_agent_ids": list(cell["extra"]["changed_agent_ids"]),
                "target_agent_ids": list(cell["extra"]["target_agent_ids"]),
                "no_untargeted_spillover": bool(spillover["passed"]),
                "expected_actions": dict(
                    cell["process_profile"]["expected_actions"]
                ),
                "actual_actions": dict(cell["process_profile"]["actual_actions"]),
                "cell_result_path": str(cell_path),
                "model_trace_path": str(run_dir / "model_trace.jsonl"),
                "policy_trace_path": str(run_dir / "policy_trace.jsonl"),
            }
        )

    by_condition = {str(cell["condition"]): cell for cell in cells}
    expected_changes = {
        "no_policy": [],
        "real_policy": target_agents,
        "placebo_policy": [],
    }
    registered_outcomes_pass = all(
        cell["measurement_valid"]
        and cell["model_contract_pass"]
        and cell["full_pass"] == 1
        and cell["no_untargeted_spillover"]
        and sorted(cell["changed_agent_ids"])
        == expected_changes[str(cell["condition"])]
        for cell in cells
    )
    design_adherent = (
        len(cells) == 3
        and int(budget.snapshot()["calls_used"]) == MAX_CALLS
        and all(int(cell["calls"]) == 4 for cell in cells)
    )
    first_errors = Counter(str(cell["first_error"]) for cell in cells)
    no_policy_rate = float(by_condition["no_policy"]["behavior_change_rate"])
    real_policy_rate = float(by_condition["real_policy"]["behavior_change_rate"])
    placebo_rate = float(by_condition["placebo_policy"]["behavior_change_rate"])
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
        "registered_design_adherent": design_adherent,
        "all_registered_outcomes_pass": registered_outcomes_pass,
        "n_cells": len(cells),
        "target_agent_ids": target_agents,
        "FullPassByCondition": {
            condition: int(by_condition[condition]["full_pass"])
            for condition in CONDITIONS
        },
        "BehaviorChangeRateByCondition": {
            condition: float(by_condition[condition]["behavior_change_rate"])
            for condition in CONDITIONS
        },
        "causal_contrasts": {
            "real_minus_no_policy": round(real_policy_rate - no_policy_rate, 4),
            "real_minus_placebo": round(real_policy_rate - placebo_rate, 4),
            "placebo_minus_no_policy": round(placebo_rate - no_policy_rate, 4),
        },
        "model_contract_rate": _rate(
            [bool(cell["model_contract_pass"]) for cell in cells]
        ),
        "first_error_counts": dict(sorted(first_errors.items())),
        "budget": budget.snapshot(),
        "cells": cells,
    }
    if not client.info.live:
        summary["gate"] = (
            "offline_minimal_calibration_pass"
            if design_adherent and registered_outcomes_pass
            else "offline_minimal_calibration_failed"
        )
    else:
        summary["gate"] = "registered_minimal_pilot_recorded"
    (out / "MINIMAL_MANIFEST.yaml").write_text(
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
        default=BRIDGE_ROOT / "output" / "model_pilot_t5_minimal_v1",
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
    return 0 if summary.get("gate") != "offline_minimal_calibration_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
