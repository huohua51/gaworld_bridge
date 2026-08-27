"""Run preregistered T5-v3 eligibility-scope repeats 1/2."""

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
from exp_gm_t5_02.run_matrix import _eval_evidence
from exp_gm_t5_03.loader import TASK_IDS, load_tasks
from exp_gm_t5_03.semantics import POLICY_STATES
from model_pilot.t5_v3 import PROMPT_PROTOCOL, run_cell
from model_pilot.t5_v3_fixture import oracle_fixture_client
from model_pilot.t5_v3_scorer import SCORER_VERSION, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

REGISTRATION_PATH = (
    Path(__file__).with_name("registrations")
    / "T5_ELIGIBILITY_SCOPE_GLM52_REPEATS_v1.yaml"
)
REPEAT_IDS = (1, 2)
TRACK = "full"
MAX_CALLS = 72
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
    if tuple(design.get("repeat_ids") or ()) != REPEAT_IDS:
        errors.append("registered_repeat_order_mismatch")
    if str(design.get("track") or "") != TRACK:
        errors.append("registered_track_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("registered_call_budget_mismatch")
    if str(design.get("prompt_protocol") or "") != PROMPT_PROTOCOL:
        errors.append("registered_prompt_protocol_mismatch")
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


def _gate(cell: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(item for item in cell["gates"] if item["gate_id"] == gate_id)


def _observation(
    *,
    task_id: str,
    policy_state: str,
    repeat_id: int,
    calls: int,
    cell: dict[str, Any],
    cell_path: Path,
    model_trace_path: Path,
    policy_trace_path: Path,
) -> dict[str, Any]:
    process = cell.get("process_profile") or {}
    scope_decisions = process.get("scope_decisions") or []
    return {
        "task_id": task_id,
        "policy_state": policy_state,
        "repeat_id": repeat_id,
        "calls": calls,
        "measurement_valid": bool(cell["measurement_valid"]),
        "scope_prompt_unambiguous": bool(
            _gate(cell, "scope_prompt_unambiguous")["passed"]
        ),
        "model_contract_pass": bool(
            _gate(cell, "model_responses_structured")["passed"]
        ),
        "scope_semantics_pass": bool(
            _criterion(cell, "resident_scope_semantics_correct")["passed"]
        ),
        "resident_directive_pass": bool(
            _criterion(cell, "resident_directive_followed")["passed"]
        ),
        "policy_response_pass": bool(
            _criterion(cell, "policy_response_correct")["passed"]
        ),
        "no_untargeted_spillover": bool(
            _criterion(cell, "no_untargeted_spillover")["passed"]
        ),
        "full_pass": cell["full_pass"],
        "first_error": str(process.get("first_error")),
        "behavior_change_rate": float(cell["extra"]["behavior_change_rate"]),
        "changed_agent_ids": list(cell["extra"]["changed_agent_ids"]),
        "actual_actions": dict(process.get("actual_actions") or {}),
        "scope_outputs": {
            str(item.get("agent_id") or ""): dict(item.get("actual") or {})
            for item in scope_decisions
        },
        "prompt_sha256_by_resident": dict(
            cell["extra"].get("prompt_sha256_by_resident") or {}
        ),
        "cell_result_path": str(cell_path),
        "model_trace_path": str(model_trace_path),
        "policy_trace_path": str(policy_trace_path),
    }


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
    observations: list[dict[str, Any]] = []

    for task_id in TASK_IDS:
        task = tasks[task_id]
        for policy_state in POLICY_STATES:
            for repeat_id in REPEAT_IDS:
                run_id = (
                    f"model_v3_{task_id}_{policy_state}_{TRACK}_r{repeat_id}"
                )
                run_dir = out / "runs" / run_id
                model_trace_path = run_dir / "model_trace.jsonl"
                policy_trace_path = run_dir / "policy_trace.jsonl"
                before = int(budget.snapshot()["calls_used"])
                runner = RecordedModelRunner(
                    model_trace_path,
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
                    repeat_id=repeat_id,
                    loop=loop,
                    eval_mode_evidence=evidence,
                )
                cell_path = run_dir / "cell_result.json"
                cell_path.write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                cells.append(cell)
                observations.append(
                    _observation(
                        task_id=task_id,
                        policy_state=policy_state,
                        repeat_id=repeat_id,
                        calls=int(budget.snapshot()["calls_used"]) - before,
                        cell=cell,
                        cell_path=cell_path,
                        model_trace_path=model_trace_path,
                        policy_trace_path=policy_trace_path,
                    )
                )

    by_pair: dict[str, dict[str, Any]] = {}
    for task_id in TASK_IDS:
        for policy_state in POLICY_STATES:
            values = [
                item
                for item in observations
                if item["task_id"] == task_id
                and item["policy_state"] == policy_state
            ]
            values.sort(key=lambda item: int(item["repeat_id"]))
            prompt_stable = all(
                values[0]["prompt_sha256_by_resident"]
                == item["prompt_sha256_by_resident"]
                for item in values[1:]
            )
            outcome_exact = all(
                values[0]["actual_actions"] == item["actual_actions"]
                and values[0]["scope_outputs"] == item["scope_outputs"]
                and values[0]["full_pass"] == item["full_pass"]
                for item in values[1:]
            )
            by_pair[f"{task_id}:{policy_state}"] = {
                "repeat_ids": [int(item["repeat_id"]) for item in values],
                "prompt_stable_across_repeats": prompt_stable,
                "outcome_exact_agreement": outcome_exact,
                "full_pass_rate": _rate(
                    [item["full_pass"] == 1 for item in values]
                ),
                "scope_semantics_rate": _rate(
                    [bool(item["scope_semantics_pass"]) for item in values]
                ),
                "resident_directive_rate": _rate(
                    [bool(item["resident_directive_pass"]) for item in values]
                ),
                "behavior_change_rate": [
                    float(item["behavior_change_rate"]) for item in values
                ],
            }

    by_state = {
        state: [item for item in observations if item["policy_state"] == state]
        for state in POLICY_STATES
    }
    full_pass = {
        state: _rate([item["full_pass"] == 1 for item in by_state[state]])
        for state in POLICY_STATES
    }
    behavior_change = {
        state: round(
            sum(float(item["behavior_change_rate"]) for item in by_state[state])
            / len(by_state[state]),
            4,
        )
        for state in POLICY_STATES
    }
    first_errors = Counter(item["first_error"] for item in observations)
    all_pass = all(
        item["measurement_valid"]
        and item["scope_prompt_unambiguous"]
        and item["model_contract_pass"]
        and item["scope_semantics_pass"]
        and item["resident_directive_pass"]
        and item["policy_response_pass"]
        and item["no_untargeted_spillover"]
        and item["full_pass"] == 1
        for item in observations
    )
    design_adherent = (
        len(observations) == 18
        and int(budget.snapshot()["calls_used"]) == MAX_CALLS
        and all(int(item["calls"]) == 4 for item in observations)
        and all(item["prompt_stable_across_repeats"] for item in by_pair.values())
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
        "prompt_protocol": PROMPT_PROTOCOL,
        "ranking_eligible": False,
        "registered_design_adherent": design_adherent,
        "all_registered_outcomes_pass": all_pass,
        "new_cells": len(observations),
        "FullPassByPolicyState": full_pass,
        "BehaviorChangeRateByPolicyState": behavior_change,
        "causal_contrasts": {
            "binding_minus_absence": round(
                behavior_change["binding"] - behavior_change["absence"], 4
            ),
            "binding_minus_nonbinding": round(
                behavior_change["binding"] - behavior_change["nonbinding"], 4
            ),
            "nonbinding_minus_absence": round(
                behavior_change["nonbinding"] - behavior_change["absence"], 4
            ),
        },
        "scope_prompt_rate": _rate(
            [item["scope_prompt_unambiguous"] for item in observations]
        ),
        "model_contract_rate": _rate(
            [item["model_contract_pass"] for item in observations]
        ),
        "scope_semantics_rate": _rate(
            [item["scope_semantics_pass"] for item in observations]
        ),
        "resident_directive_rate": _rate(
            [item["resident_directive_pass"] for item in observations]
        ),
        "policy_response_rate": _rate(
            [item["policy_response_pass"] for item in observations]
        ),
        "repeat_exact_agreement_rate": _rate(
            [item["outcome_exact_agreement"] for item in by_pair.values()]
        ),
        "first_error_counts": dict(sorted(first_errors.items())),
        "by_task_policy_state": by_pair,
        "budget": budget.snapshot(),
        "cells": observations,
    }
    if not client.info.live:
        summary["gate"] = (
            "offline_t5_v3_repeat_calibration_pass"
            if design_adherent and all_pass
            else "offline_t5_v3_repeat_calibration_failed"
        )
    else:
        summary["gate"] = "registered_t5_v3_repeat_pilot_recorded"
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
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
        default=BRIDGE_ROOT / "output" / "model_pilot_t5_v3_repeats_v1",
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
    return (
        1
        if summary.get("gate") == "offline_t5_v3_repeat_calibration_failed"
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
