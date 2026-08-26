"""Evidence-only scorer for the T5 seed-0 model pilot."""

from __future__ import annotations

from typing import Any

from benchmark_core.result import RunContext, compose_cell
from model_pilot.evidence import model_trace_evidence, read_jsonl
from v0_first_batch.schema import CriterionResult, GateResult

WORKFLOW_ID = "model_pilot_t5_v1"
SCORER_VERSION = "model-pilot-t5-scorer-v1"


def _expected_actions(task: dict[str, Any], condition: str) -> dict[str, str]:
    target_groups = {str(group) for group in task["target_groups"]}
    return {
        str(resident["agent_id"]): (
            str(task["target_action"])
            if condition == "real_policy" and str(resident["group"]) in target_groups
            else "keep_current"
        )
        for resident in task["residents"]
    }


def score_cell(
    *,
    task: dict[str, Any],
    condition: str,
    track: str,
    seed: int,
    loop: dict[str, Any],
    eval_mode_evidence: dict[str, Any],
) -> dict[str, Any]:
    policy_rows = read_jsonl(str(loop.get("trace_path") or ""))
    model = model_trace_evidence(str(loop.get("model_trace_path") or ""))
    event_names = [str(row.get("event") or "") for row in policy_rows]
    action_rows = [
        row for row in policy_rows if row.get("event") == "resident_action_submitted"
    ]
    actual = {
        str(row.get("agent_id") or ""): str(
            (row.get("action_record") or {}).get("action") or ""
        )
        for row in action_rows
    }
    expected = _expected_actions(task, condition)
    response_correct = actual == expected
    changed = {
        str(row.get("agent_id") or "")
        for row in action_rows
        if dict(row.get("state_after") or {}) != dict(row.get("state_before") or {})
    }
    target_groups = {str(group) for group in task["target_groups"]}
    target_agents = {
        str(resident["agent_id"])
        for resident in task["residents"]
        if str(resident["group"]) in target_groups
    }
    expected_changed = target_agents if condition == "real_policy" else set()
    effect_correct = changed == expected_changed
    policy_expected = condition != "no_policy"
    registered = "policy_registered" in event_names
    activated = "policy_activated" in event_names
    perception_count = sum(1 for name in event_names if name == "policy_perceived")
    delivery_complete = not policy_expected or perception_count == len(expected)
    mechanism_active = not policy_expected or (
        track == "full" and registered and activated and delivery_complete
    )
    allowed_denials = {
        "policy_not_active",
        "action_evidence_not_perceived",
        "action_not_registered",
    }
    denials = {
        str(row.get("reason") or "")
        for row in policy_rows
        if row.get("event") == "denied"
    }
    execution_valid = bool(policy_rows) and denials <= allowed_denials
    all_actions_present = set(actual) == set(expected) and all(actual.values())
    first_error = "none"
    if not model["contract_ok"]:
        first_error = "model_response_contract_invalid"
    elif not response_correct:
        first_error = "resident_policy_response_incorrect"
    elif not effect_correct:
        first_error = "policy_effect_or_spillover_incorrect"
    run_id = f"model_{task['id']}_{condition}_{track}_s{seed}"
    evidence_ids = [str(loop["trace_path"]), str(loop["model_trace_path"])]
    evidence_ids.extend(model["evidence_ids"])
    evidence_ids.extend(
        str((row.get("action_record") or {}).get("action_id"))
        for row in action_rows
        if (row.get("action_record") or {}).get("action_id")
    )
    context = RunContext(
        run_id=run_id,
        task_id=str(task["id"]),
        task_family="T5",
        mechanism_condition=f"M1-M4-M8:{condition}:{track}",
        variant=condition,
        seed=seed,
        track=track,
        model_version=str(model["model_version"]),
        temperature=float(model["temperature"]),
        budget={"model_calls": int(model["calls"])},
        environment_version="gaworld-urban-policy-v1",
        trace_version="urban-policy-and-model-jsonl-v1",
        scorer_version=SCORER_VERSION,
        evidence_id=f"bundle:{run_id}",
    )
    cell = compose_cell(
        workflow_id=WORKFLOW_ID,
        context=context,
        eval_mode_evidence=eval_mode_evidence,
        measurement_gates=[
            GateResult("policy_trace_parseable", bool(policy_rows), layer="R0"),
            GateResult("model_trace_parseable", model["trace_parseable"], layer="R0"),
            GateResult("execution_valid", execution_valid, layer="R0"),
            GateResult(
                "policy_mechanism_activated",
                mechanism_active,
                layer="R0",
                detail=(
                    f"registered={registered},activated={activated},"
                    f"perceptions={perception_count}"
                ),
            ),
        ],
        artifact_gates=[
            GateResult(
                "model_responses_structured",
                model["contract_ok"],
                layer="R1",
                detail=",".join(model["errors"]),
            ),
            GateResult("resident_actions_complete", all_actions_present, layer="R1"),
        ],
        criteria=[
            CriterionResult(
                "policy_response_correct",
                "R2",
                "registered_population_oracle",
                True,
                1.0 if response_correct and effect_correct else 0.0,
                passed=response_correct and effect_correct,
                critical=True,
                evidence_ids=evidence_ids,
                detail=f"expected={expected} actual={actual}",
            ),
            CriterionResult(
                "no_untargeted_spillover",
                "R3",
                "state_delta",
                True,
                1.0 if changed <= target_agents else 0.0,
                passed=changed <= target_agents,
                evidence_ids=[str(loop["trace_path"])],
            ),
        ],
        process_profile={
            "first_error": first_error,
            "events": event_names,
            "expected_actions": expected,
            "actual_actions": actual,
            "model_errors": model["errors"],
        },
        extra={
            "phase": "model_seed0_pilot",
            "provider": model["provider"],
            "model_calls": model["calls"],
            "condition": condition,
            "behavior_change_rate": len(changed) / len(expected),
            "changed_agent_ids": sorted(changed),
            "target_agent_ids": sorted(target_agents),
            "base_release": "benchmark-v1.1-rule",
        },
    )
    cell["ranking_eligible"] = False
    return cell
