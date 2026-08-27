"""C1-04 scorer: separate measurement validity from retry success."""

from __future__ import annotations

from typing import Any

from exp_gm_c1_04.loader import private_for
from v0_first_batch.schema import CriterionResult, GateResult, compose

WORKFLOW_ID = "exp_gm_c1_04_platform_plan_retry"
SCORER_VERSION = "c1-platform-plan-v4.0"


def _first_error(loop: dict[str, Any], expected: dict[str, Any]) -> str:
    if not all(loop["model_response_ok"]):
        return "model_response_invalid"
    if loop["model_generated_identifier"]:
        return "model_attempted_platform_identifier"
    if loop["initial_assignments"] != expected["initial"]:
        return "initial_assignment_incorrect"
    if bool(loop["nack_path"]) != bool(expected["nack_expected"]):
        return "nack_path_mismatch"
    if (loop["protection_registration"] or {}).get("spec_version") != "spec-002":
        return "spec_revision_missing"
    if (loop["stale_initial_confirmation"] or {}).get("reason") != "stale_plan_spec":
        return "stale_plan_not_rejected"
    if loop["retry_assignments"] != expected["final"]:
        return "retry_assignment_incorrect"
    if not (loop["final_proposal"] or {}).get("accepted"):
        return "retry_not_accepted"
    plan = loop.get("accepted_plan") or {}
    if not plan.get("plan_id") or plan.get("spec_version") != "spec-002":
        return "platform_plan_not_stamped"
    if not all((loop["confirmations"].get(agent) or {}).get("ok") for agent in ("agent_a", "agent_b")):
        return "agent_confirmation_failed"
    if loop["world"].get("by_agent") != expected["final"]:
        return "execution_deviated_from_plan"
    return "none"


def score_cell(
    *,
    task: dict[str, Any],
    variant: str,
    seed: int,
    loop: dict[str, Any],
) -> dict[str, Any]:
    expected = task["oracle"][variant]
    private = {
        agent: private_for(task, agent, variant)
        for agent in ("agent_a", "agent_b")
    }
    reports_faithful = all(
        loop["reports"].get(agent)
        == {
            "agent_id": agent,
            "feasible": private[agent]["feasible"],
            "preferred": private[agent]["preferred"],
        }
        for agent in ("agent_a", "agent_b")
    )
    model_structured = len(loop["model_response_ok"]) == 6 and all(loop["model_response_ok"])
    budget_valid = (loop["model_summary"] or {}).get("calls") == 6
    identifier_owned = not loop["model_generated_identifier"]
    initial_correct = loop["initial_assignments"] == expected["initial"]
    nack_correct = bool(loop["nack_path"]) == bool(expected["nack_expected"])
    spec_revised = (loop["protection_registration"] or {}).get("spec_version") == "spec-002"
    stale_rejected = (loop["stale_initial_confirmation"] or {}).get("reason") == "stale_plan_spec"
    retry_correct = loop["retry_assignments"] == expected["final"]
    accepted = bool((loop["final_proposal"] or {}).get("accepted"))
    plan = loop.get("accepted_plan") or {}
    platform_stamped = bool(plan.get("plan_id")) and plan.get("spec_version") == "spec-002"
    confirmations_ok = all(
        (loop["confirmations"].get(agent) or {}).get("ok")
        for agent in ("agent_a", "agent_b")
    )
    world_correct = loop["world"].get("by_agent") == expected["final"]
    conflict_free = not loop["world"].get("duplicates") and len(loop["world"].get("by_agent") or {}) == 2
    error = _first_error(loop, expected)
    result = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=f"c1_v4_{task['id']}_{variant}_full_s{seed}",
        measurement_gates=[
            GateResult("model_responses_structured", model_structured, layer="R0"),
            GateResult("model_call_budget_valid", budget_valid, layer="R0"),
            GateResult("private_reports_faithful", reports_faithful, layer="R0"),
            GateResult("private_context_isolated", bool(loop["private_isolated"]), layer="R0"),
            GateResult("coordinator_did_not_execute", bool(loop["coordinator_execution_denied"]), layer="R0"),
            GateResult("model_did_not_issue_identifiers", identifier_owned, layer="R0"),
            GateResult("nack_did_not_leak_repair_slot", not loop["nack_leaked_repair_slot"], layer="R0"),
        ],
        artifact_gates=[
            GateResult("accepted_platform_plan_exists", bool(plan), layer="R1"),
            GateResult("two_confirmed_claims_exist", len(loop["world"].get("by_agent") or {}) == 2, layer="R1"),
        ],
        criteria=[
            CriterionResult("phase1_assignment_correct", "R2", "frozen_oracle", True, float(initial_correct), passed=initial_correct, critical=True),
            CriterionResult("registered_nack_behavior_correct", "R2", "expected_path", True, float(nack_correct), passed=nack_correct, critical=True),
            CriterionResult("spec_revision_advanced", "R2", "registry_trace", True, float(spec_revised), passed=spec_revised, critical=True),
            CriterionResult("stale_plan_rejected", "R2", "registry_confirmation", True, float(stale_rejected), passed=stale_rejected, critical=True),
            CriterionResult("retry_assignment_correct", "R2", "frozen_oracle", True, float(retry_correct), passed=retry_correct, critical=True),
            CriterionResult("retry_accepted_without_auto_repair", "R2", "assignment_trace", True, float(accepted), passed=accepted, critical=True),
            CriterionResult("platform_plan_stamped", "R2", "plan_registry", True, float(platform_stamped), passed=platform_stamped, critical=True),
            CriterionResult("agent_confirmations_bound", "R2", "plan_registry", True, float(confirmations_ok), passed=confirmations_ok, critical=True),
            CriterionResult("final_world_matches_plan", "R2", "world_state", True, float(world_correct), passed=world_correct, critical=True),
            CriterionResult("actual_final_conflict_free", "R2", "occupancy", True, float(conflict_free), passed=conflict_free, critical=True),
        ],
        process_profile={
            "first_error": error,
            "violations": loop["violations"],
            "delivery_events": loop["delivery_events"],
            "assignment_events": loop["assignment_events"],
        },
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": "full",
            "seed": seed,
            "first_error": error,
            "nack_path_coverage": bool(loop["nack_path"]),
            "retry_recovery_success": bool(retry_correct and accepted and world_correct),
            "platform_identifier_ownership": identifier_owned and platform_stamped,
            "spec_revision_advanced": spec_revised,
            "stale_plan_rejected": stale_rejected,
            "got_initial": loop["initial_assignments"],
            "got_final": loop["world"].get("by_agent") or {},
            "want_initial": expected["initial"],
            "want_final": expected["final"],
            "model_evidence_ids": loop["model_evidence_ids"],
            "ranking_note": "C1-04 fresh-surface platform repair regression; not a leaderboard",
        },
    )
    result["ranking_eligible"] = False
    return result
