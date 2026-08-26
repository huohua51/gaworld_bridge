"""Independent scorer for T5 policy causal-chain calibration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark_core.result import RunContext, compose_cell
from v0_first_batch.schema import CriterionResult, GateResult

WORKFLOW_ID = "exp_gm_t5_01_policy"
SCORER_VERSION = "t5-01-scorer-v1"


def _trace_rows(path: str) -> list[dict[str, Any]]:
    trace = Path(path)
    if not trace.is_file() or trace.stat().st_size == 0:
        return []
    return [
        json.loads(line)
        for line in trace.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _expected_actions(task: dict[str, Any], condition: str) -> dict[str, str]:
    targets = {str(group) for group in task["target_groups"]}
    return {
        str(resident["agent_id"]): (
            str(task["target_action"])
            if condition == "real_policy" and str(resident["group"]) in targets
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
    trace_rows = _trace_rows(str(loop.get("trace_path") or ""))
    event_names = [str(row.get("event") or "") for row in trace_rows]
    expected = _expected_actions(task, condition)
    action_rows = [
        row for row in trace_rows if row.get("event") == "resident_action_submitted"
    ]
    actual = {
        str(row.get("agent_id") or ""): str(
            (row.get("action_record") or {}).get("action") or ""
        )
        for row in action_rows
    }
    response_correct = actual == expected
    all_actions_present = set(actual) == set(expected) and all(actual.values())
    policy_expected = condition != "no_policy"
    policy_registered = "policy_registered" in event_names
    policy_activated = "policy_activated" in event_names
    perceptions = [row for row in trace_rows if row.get("event") == "policy_perceived"]
    delivery_complete = not policy_expected or len(perceptions) == len(expected)
    mechanism_active = not policy_expected or (
        track == "full" and policy_registered and policy_activated and delivery_complete
    )
    expected_denials = (
        {"policy_not_active"} if policy_expected and track != "full" else set()
    )
    denials = {
        str(row.get("reason") or "")
        for row in trace_rows
        if row.get("event") == "denied"
    }
    execution_valid = bool(trace_rows) and denials <= expected_denials
    changed = {
        str(row.get("agent_id") or "")
        for row in action_rows
        if dict(row.get("state_after") or {}) != dict(row.get("state_before") or {})
    }
    target_groups = {str(item) for item in task["target_groups"]}
    target_agents = {
        str(resident["agent_id"])
        for resident in task["residents"]
        if str(resident["group"]) in target_groups
    }
    expected_changed = target_agents if condition == "real_policy" else set()
    effect_correct = changed == expected_changed
    first_error = "none"
    if not response_correct:
        first_error = "resident_policy_response_incorrect"
    elif not effect_correct:
        first_error = "policy_effect_or_spillover_incorrect"
    run_id = f"{task['id']}_{condition}_{track}_s{seed}"
    trace_id = str(loop["trace_path"])
    action_ids = [
        str((row.get("action_record") or {}).get("action_id"))
        for row in action_rows
        if (row.get("action_record") or {}).get("action_id")
    ]
    context = RunContext(
        run_id=run_id,
        task_id=str(task["id"]),
        task_family="T5",
        mechanism_condition=f"M1-M4-M8:{condition}:{track}",
        variant=condition,
        seed=seed,
        track=track,
        model_version="rule",
        temperature=0,
        budget={"logical_calls": 0, "resident_actions": len(expected)},
        environment_version="gaworld-urban-policy-v1",
        trace_version="urban-policy-jsonl-v1",
        scorer_version=SCORER_VERSION,
        evidence_id=f"bundle:{run_id}",
    )
    cell = compose_cell(
        workflow_id=WORKFLOW_ID,
        context=context,
        eval_mode_evidence=eval_mode_evidence,
        measurement_gates=[
            GateResult("execution_valid", execution_valid, layer="R0"),
            GateResult("trace_parseable", bool(trace_rows), layer="R0"),
            GateResult(
                "policy_mechanism_activated",
                mechanism_active,
                layer="R0",
                detail=(
                    f"registered={policy_registered},activated={policy_activated},"
                    f"perceptions={len(perceptions)}"
                ),
            ),
        ],
        artifact_gates=[
            GateResult("resident_actions_complete", all_actions_present, layer="R1")
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
                evidence_ids=[trace_id, *action_ids],
                detail=f"expected={expected} actual={actual}",
            ),
            CriterionResult(
                "no_untargeted_spillover",
                "R3",
                "state_delta",
                True,
                1.0 if changed <= target_agents else 0.0,
                passed=changed <= target_agents,
                evidence_ids=[trace_id],
            ),
        ],
        process_profile={
            "first_error": first_error,
            "events": event_names,
            "expected_actions": expected,
            "actual_actions": actual,
        },
        extra={
            "condition": condition,
            "behavior_change_rate": len(changed) / len(expected),
            "changed_agent_ids": sorted(changed),
            "target_agent_ids": sorted(target_agents),
            "rule_calibration": True,
        },
    )
    cell["ranking_eligible"] = False
    return cell
