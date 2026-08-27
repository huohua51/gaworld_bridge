"""Frozen C1-05 scorer."""

from __future__ import annotations

from typing import Any

from exp_gm_c1_05.loader import private_for
from v0_first_batch.schema import CriterionResult, GateResult, compose

WORKFLOW_ID = "exp_gm_c1_05_authoritative_retry"
SCORER_VERSION = "c1-authoritative-current-spec-v5.0"


def _first_error(loop: dict[str, Any], want: dict[str, Any]) -> str:
    if not all(loop["model_ok"]):
        return "model_response_invalid"
    if loop["model_generated_identifier"]:
        return "model_attempted_platform_identifier"
    if loop["initial_assignments"] != want["initial"]:
        return "initial_assignment_incorrect"
    if bool(loop["priority_nack_path"]) != bool(want["nack_expected"]):
        return "priority_nack_path_mismatch"
    if (loop["registration"] or {}).get("spec_version") != "spec-002":
        return "spec_revision_missing"
    if (loop["stale_confirmation"] or {}).get("reason") != "stale_plan_spec":
        return "stale_plan_not_rejected"
    if loop["retry_assignments"] != want["final"]:
        return "retry_assignment_incorrect"
    if not (loop["final_proposal"] or {}).get("accepted"):
        return "retry_not_accepted"
    if not all((loop["confirmations"].get(agent) or {}).get("ok") for agent in ("agent_a", "agent_b")):
        return "agent_confirmation_failed"
    if loop["world"].get("by_agent") != want["final"]:
        return "execution_deviated_from_plan"
    return "none"


def score_cell(task: dict[str, Any], variant: str, loop: dict[str, Any]) -> dict[str, Any]:
    want = task["oracle"][variant]
    privates = {agent: private_for(task, agent, variant) for agent in ("agent_a", "agent_b")}
    reports_ok = all(
        loop["reports"].get(agent)
        == {key: privates[agent][key] for key in ("agent_id", "feasible", "preferred")}
        for agent in ("agent_a", "agent_b")
    )
    structured = len(loop["model_ok"]) == 6 and all(loop["model_ok"])
    initial_ok = loop["initial_assignments"] == want["initial"]
    nack_ok = bool(loop["priority_nack_path"]) == bool(want["nack_expected"])
    no_other_nack = bool(loop["any_nack_path"]) == bool(want["nack_expected"])
    spec_ok = (loop["registration"] or {}).get("spec_version") == "spec-002"
    stale_ok = (loop["stale_confirmation"] or {}).get("reason") == "stale_plan_spec"
    retry_ok = loop["retry_assignments"] == want["final"]
    accepted = bool((loop["final_proposal"] or {}).get("accepted"))
    plan = loop.get("accepted_plan") or {}
    platform_plan = bool(plan.get("plan_id")) and plan.get("spec_version") == "spec-002"
    confirmations = all((loop["confirmations"].get(agent) or {}).get("ok") for agent in ("agent_a", "agent_b"))
    world_ok = loop["world"].get("by_agent") == want["final"] and not loop["world"].get("duplicates")
    error = _first_error(loop, want)
    result = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=f"c1_v5_{task['id']}_{variant}_full_s0",
        measurement_gates=[
            GateResult("model_responses_structured", structured, layer="R0"),
            GateResult("fixed_six_call_budget", (loop["model_summary"] or {}).get("calls") == 6, layer="R0"),
            GateResult("private_reports_faithful", reports_ok, layer="R0"),
            GateResult("private_context_isolated", bool(loop["private_isolated"]), layer="R0"),
            GateResult("coordinator_did_not_execute", bool(loop["coordinator_execution_denied"]), layer="R0"),
            GateResult("model_did_not_issue_identifiers", not loop["model_generated_identifier"], layer="R0"),
            GateResult("nack_did_not_leak_repair_slot", not loop["nack_leaked_repair_slot"], layer="R0"),
        ],
        artifact_gates=[
            GateResult("current_spec_plan_exists", bool(plan), layer="R1"),
            GateResult("two_confirmed_claims_exist", len(loop["world"].get("by_agent") or {}) == 2, layer="R1"),
        ],
        criteria=[
            CriterionResult("phase1_assignment_correct", "R2", "oracle", True, float(initial_ok), passed=initial_ok, critical=True),
            CriterionResult("priority_nack_behavior_correct", "R2", "trace", True, float(nack_ok), passed=nack_ok, critical=True),
            CriterionResult("no_unregistered_nack", "R2", "trace", True, float(no_other_nack), passed=no_other_nack, critical=True),
            CriterionResult("spec_revision_advanced", "R2", "registry", True, float(spec_ok), passed=spec_ok, critical=True),
            CriterionResult("stale_plan_rejected", "R2", "registry", True, float(stale_ok), passed=stale_ok, critical=True),
            CriterionResult("authoritative_retry_correct", "R2", "oracle", True, float(retry_ok), passed=retry_ok, critical=True),
            CriterionResult("retry_accepted", "R2", "validator", True, float(accepted), passed=accepted, critical=True),
            CriterionResult("platform_plan_stamped", "R2", "registry", True, float(platform_plan), passed=platform_plan, critical=True),
            CriterionResult("agents_bound_to_plan", "R2", "registry", True, float(confirmations), passed=confirmations, critical=True),
            CriterionResult("world_matches_current_plan", "R2", "world", True, float(world_ok), passed=world_ok, critical=True),
        ],
        process_profile={"first_error": error, "violations": loop["violations"]},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": "full",
            "seed": 0,
            "first_error": error,
            "priority_nack_path": bool(loop["priority_nack_path"]),
            "retry_recovery_success": bool(retry_ok and accepted and world_ok),
            "platform_identifier_ownership": bool(not loop["model_generated_identifier"] and platform_plan),
            "spec_revision_advanced": spec_ok,
            "stale_plan_rejected": stale_ok,
            "got_initial": loop["initial_assignments"],
            "got_retry": loop["retry_assignments"],
            "got_world": loop["world"].get("by_agent") or {},
            "want_initial": want["initial"],
            "want_final": want["final"],
            "model_evidence_ids": loop["model_evidence_ids"],
        },
    )
    result["ranking_eligible"] = False
    return result
