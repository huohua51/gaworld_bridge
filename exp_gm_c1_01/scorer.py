"""C1-01 scoring. World occupancy, not verbal agreement."""

from __future__ import annotations

from typing import Any

from exp_gm_c1_01.contract import PLAN_VERSION
from exp_gm_c1_01.loader import agent_private, oracle_plan
from v0_first_batch.schema import CriterionResult, GateResult, compose

FIRST_ERRORS = (
    "private_constraint_not_reported",
    "constraint_message_not_delivered",
    "conflict_not_detected",
    "invalid_joint_plan",
    "agent_rejected_assignment",
    "plan_version_inconsistent",
    "duplicate_resource_claim",
    "execution_deviated_from_plan",
    "final_state_conflict",
    "none",
)


def first_error(*, track: str, variant: str, loop: dict[str, Any], want: dict[str, Any], private: dict[str, dict[str, Any]]) -> str:
    reports = loop.get("reports") or {}
    report_errors = loop.get("report_errors") or {}
    if report_errors.get("agent_a") != "ok" or report_errors.get("agent_b") != "ok":
        return "private_constraint_not_reported"
    if not reports.get("agent_a") or not reports.get("agent_b"):
        return "private_constraint_not_reported"
    if track == "drop" or (track == "multi" and not loop.get("b_delivered")):
        if track == "drop" or not loop.get("b_delivered"):
            return "constraint_message_not_delivered"
    plan = loop.get("plan") or {}
    if loop.get("plan_error") != "ok":
        return "invalid_joint_plan"
    if bool(plan.get("conflict")) != bool(want.get("conflict")):
        return "conflict_not_detected"
    assignments = plan.get("assignments") or {}
    if assignments.get("agent_a") != want["assignments"]["agent_a"] or assignments.get("agent_b") != want["assignments"]["agent_b"]:
        return "invalid_joint_plan"
    commits = loop.get("commits") or {}
    commit_errors = loop.get("commit_errors") or {}
    versions = {str((commits.get(agent) or {}).get("plan_version") or "") for agent in ("agent_a", "agent_b")}
    if commit_errors.get("agent_a") != "ok" or commit_errors.get("agent_b") != "ok":
        return "agent_rejected_assignment"
    if any(not (commits.get(agent) or {}).get("confirm") for agent in ("agent_a", "agent_b")):
        return "agent_rejected_assignment"
    if versions != {PLAN_VERSION}:
        return "plan_version_inconsistent"
    world = loop.get("world") or {}
    if world.get("duplicates"):
        return "duplicate_resource_claim"
    by_agent = world.get("by_agent") or {}
    for agent in ("agent_a", "agent_b"):
        if by_agent.get(agent) != assignments.get(agent):
            return "execution_deviated_from_plan"
        if by_agent.get(agent) not in set(private[agent]["feasible"]):
            return "execution_deviated_from_plan"
    if len(set(by_agent.values())) < 2:
        return "final_state_conflict"
    return "none"


def score_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    repeat_id: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    want = oracle_plan(task, variant)
    private = {"agent_a": agent_private(task, "agent_a", variant), "agent_b": agent_private(task, "agent_b", variant)}
    plan = loop.get("plan") or {}
    assignments = plan.get("assignments") or {}
    world = loop.get("world") or {}
    by_agent = world.get("by_agent") or {}
    commits = loop.get("commits") or {}
    extractable = all(
        [
            (loop.get("report_errors") or {}).get("agent_a") == "ok",
            (loop.get("report_errors") or {}).get("agent_b") == "ok" or track == "direct",
            loop.get("plan_error") == "ok",
        ]
    )
    if track != "direct":
        extractable = extractable and (loop.get("commit_errors") or {}).get("agent_a") == "ok" and (loop.get("commit_errors") or {}).get("agent_b") == "ok"
    individual = all(by_agent.get(agent) in set(private[agent]["feasible"]) for agent in ("agent_a", "agent_b")) and len(by_agent) == 2
    no_conflict = not world.get("duplicates") and len(set(by_agent.values())) == 2
    if track == "direct":
        committed = loop.get("plan_error") == "ok" and assignments == want["assignments"]
        matches = by_agent == want["assignments"]
    else:
        committed = all((commits.get(agent) or {}).get("confirm") for agent in ("agent_a", "agent_b")) and {
            str((commits.get(agent) or {}).get("plan_version") or "") for agent in ("agent_a", "agent_b")
        } == {PLAN_VERSION} and assignments == want["assignments"]
        matches = by_agent == assignments == want["assignments"]
    plan_ok = assignments == want["assignments"] and bool(plan.get("conflict")) == bool(want.get("conflict"))
    drop_isolated = True if track != "drop" else bool(loop.get("b_ran")) and not loop.get("b_delivered") and bool(loop.get("drop_inbox_missing_b"))
    r0 = (
        bool(loop.get("budget_valid"))
        and extractable
        and bool(loop.get("peek_denied"))
        and bool(loop.get("env_denied"))
        and not loop.get("oracle_in_prompt")
        and not loop.get("leaks")
        and bool(loop.get("a_ran"))
        and bool(loop.get("b_ran"))
        and bool(loop.get("coordinator_ran"))
        and drop_isolated
    )
    if track == "drop":
        conditioned = False
    else:
        conditioned = bool(r0 and individual and no_conflict and committed and matches and plan_ok)
    err = first_error(track=track, variant=variant, loop=loop, want=want, private=private)
    if track == "direct":
        if not r0:
            err = "none"
        elif loop.get("plan_error") != "ok":
            err = "invalid_joint_plan"
        elif bool(plan.get("conflict")) != bool(want.get("conflict")):
            err = "conflict_not_detected"
        elif assignments != want["assignments"]:
            err = "invalid_joint_plan"
        elif world.get("duplicates"):
            err = "duplicate_resource_claim"
        elif by_agent != want["assignments"]:
            err = "execution_deviated_from_plan"
        else:
            err = "none"
    if conditioned:
        err = "none"
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0"),
            GateResult("budget_valid", bool(loop.get("budget_valid")), layer="R0"),
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("private_isolated", bool(loop.get("peek_denied")) and not loop.get("leaks"), layer="R0"),
            GateResult("drop_sender_ran", bool(loop.get("b_ran")), layer="R0"),
            GateResult("drop_receiver_isolated", drop_isolated, layer="R0"),
            GateResult("oracle_not_in_prompts", not loop.get("oracle_in_prompt"), layer="R0"),
            GateResult("environment_did_not_rewrite", bool(loop.get("env_denied")), layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult("world_exists", bool(world), layer="R1"),
        ],
        criteria=[
            CriterionResult("individual_constraint_satisfaction", "R2", "feasible_sets", True, 1.0 if individual else 0.0, passed=individual),
            CriterionResult("no_resource_conflict", "R2", "world_occupancy", True, 1.0 if no_conflict else 0.0, passed=no_conflict),
            CriterionResult("joint_plan_committed", "R2", "plan_version", True, 1.0 if committed else 0.0, passed=committed),
            CriterionResult("execution_matches_plan", "R2", "world_vs_plan", True, 1.0 if matches else 0.0, passed=matches),
            CriterionResult("oracle_conditioned_success", "R3", "joint_coordination", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "events": loop.get("events"), "budget": loop.get("budget"), "world": world},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": track,
            "repeat_id": repeat_id,
            "individual_constraint_satisfaction": individual,
            "no_resource_conflict": no_conflict,
            "joint_plan_committed": committed,
            "execution_matches_plan": matches,
            "b_ran": bool(loop.get("b_ran")),
            "b_delivered": bool(loop.get("b_delivered")),
            "budget_calls": (loop.get("budget") or {}).get("calls"),
            "budget_kinds": (loop.get("budget") or {}).get("kinds"),
            "first_error": err,
            "got": by_agent,
            "want": want["assignments"],
            "ranking_note": "coordination pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell
