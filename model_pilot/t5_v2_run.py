"""Run the preregistered T5-v2 full-track model matrix."""

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
from exp_gm_t5_02.loader import POLICY_STATES, load_tasks
from exp_gm_t5_02.run_matrix import _eval_evidence
from model_pilot.t5_v2 import run_cell
from model_pilot.t5_v2_fixture import oracle_fixture_client
from model_pilot.t5_v2_scorer import SCORER_VERSION, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

REGISTRATION_PATH = (
    Path(__file__).with_name("registrations")
    / "T5_EXPLICIT_SEMANTICS_GLM52_v2.yaml"
)
TASK_IDS = (
    "t5v2_water_restriction_001",
    "t5v2_heat_activity_001",
    "t5v2_organics_rule_001",
)
TRACK = "full"
SEED = 0
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
    design = payload.get("design") or {}
    if tuple(design.get("task_ids") or ()) != TASK_IDS:
        errors.append("registered_task_order_mismatch")
    if tuple(design.get("policy_states") or ()) != POLICY_STATES:
        errors.append("registered_policy_state_order_mismatch")
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


def _criterion(cell: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    return next(
        item for item in cell["criteria"] if item["criterion_id"] == criterion_id
    )


def run_registered(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
) -> dict[str, Any]:
    registration, registration_sha256 = _registration()
    provider = registration.get("provider") or {}
    if client.info.live:
        if client.info.provider != str(provider.get("name")):
            raise ValueError("live provider does not match preregistration")
        if client.info.model_version != str(provider.get("model")):
            raise ValueError("live model does not match preregistration")

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = {str(task["id"]): task for task in load_tasks()}
    budget = ModelCallBudget(MAX_CALLS, max_response_chars=2_000)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for task_id in TASK_IDS:
        task = tasks[task_id]
        for policy_state in POLICY_STATES:
            run_id = f"model_v2_{task_id}_{policy_state}_{TRACK}_s{SEED}"
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
            loop = run_cell(task, policy_state, TRACK, run_dir, runner)
            cell = score_cell(
                task=task,
                policy_state=policy_state,
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
            cells.append(cell)
            contract = next(
                gate
                for gate in cell["gates"]
                if gate["gate_id"] == "model_responses_structured"
            )
            summaries.append(
                {
                    "task_id": task_id,
                    "policy_state": policy_state,
                    "calls": int(budget.snapshot()["calls_used"]) - before,
                    "measurement_valid": bool(cell["measurement_valid"]),
                    "model_contract_pass": bool(contract["passed"]),
                    "policy_semantics_pass": bool(
                        _criterion(cell, "policy_semantics_correct")["passed"]
                    ),
                    "policy_response_pass": bool(
                        _criterion(cell, "policy_response_correct")["passed"]
                    ),
                    "no_untargeted_spillover": bool(
                        _criterion(cell, "no_untargeted_spillover")["passed"]
                    ),
                    "full_pass": cell["full_pass"],
                    "first_error": str(
                        cell["process_profile"].get("first_error")
                    ),
                    "behavior_change_rate": float(
                        cell["extra"]["behavior_change_rate"]
                    ),
                    "changed_agent_ids": list(cell["extra"]["changed_agent_ids"]),
                    "cell_result_path": str(cell_path),
                    "model_trace_path": str(run_dir / "model_trace.jsonl"),
                    "policy_trace_path": str(run_dir / "policy_trace.jsonl"),
                }
            )

    by_state = {
        state: [item for item in summaries if item["policy_state"] == state]
        for state in POLICY_STATES
    }
    full_pass = {
        state: _rate([item["full_pass"] == 1 for item in by_state[state]])
        for state in POLICY_STATES
    }
    behavior_change = {
        state: round(
            sum(item["behavior_change_rate"] for item in by_state[state])
            / len(by_state[state]),
            4,
        )
        for state in POLICY_STATES
    }
    binding = behavior_change["binding"]
    absence = behavior_change["absence"]
    nonbinding = behavior_change["nonbinding"]
    first_errors = Counter(item["first_error"] for item in summaries)
    all_pass = all(
        item["measurement_valid"]
        and item["model_contract_pass"]
        and item["policy_semantics_pass"]
        and item["policy_response_pass"]
        and item["no_untargeted_spillover"]
        and item["full_pass"] == 1
        for item in summaries
    )
    design_adherent = (
        len(summaries) == 9
        and int(budget.snapshot()["calls_used"]) == MAX_CALLS
        and all(int(item["calls"]) == 4 for item in summaries)
    )
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
        "prompt_protocol": "gaworld-benchmark-t5-model-v2",
        "ranking_eligible": False,
        "registered_design_adherent": design_adherent,
        "all_registered_outcomes_pass": all_pass,
        "n_cells": len(summaries),
        "FullPassByPolicyState": full_pass,
        "BehaviorChangeRateByPolicyState": behavior_change,
        "causal_contrasts": {
            "binding_minus_absence": round(binding - absence, 4),
            "binding_minus_nonbinding": round(binding - nonbinding, 4),
            "nonbinding_minus_absence": round(nonbinding - absence, 4),
        },
        "model_contract_rate": _rate(
            [item["model_contract_pass"] for item in summaries]
        ),
        "policy_semantics_rate": _rate(
            [item["policy_semantics_pass"] for item in summaries]
        ),
        "policy_response_rate": _rate(
            [item["policy_response_pass"] for item in summaries]
        ),
        "first_error_counts": dict(sorted(first_errors.items())),
        "budget": budget.snapshot(),
        "cells": summaries,
    }
    if not client.info.live:
        summary["gate"] = (
            "offline_t5_v2_calibration_pass"
            if design_adherent and all_pass
            else "offline_t5_v2_calibration_failed"
        )
    else:
        summary["gate"] = "registered_t5_v2_pilot_recorded"
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "RUN_MANIFEST.yaml").write_text(
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
        default=BRIDGE_ROOT / "output" / "model_pilot_t5_v2",
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
    return 0 if summary.get("gate") != "offline_t5_v2_calibration_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
