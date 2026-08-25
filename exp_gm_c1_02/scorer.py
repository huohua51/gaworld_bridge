"""C1-02 scoring. World occupancy is the formal result. Self-assessment is diagnostic only."""

from __future__ import annotations

from typing import Any

from exp_gm_c1_02.contract import PLAN_VERSION
from exp_gm_c1_02.loader import agent_private, oracle_plan
from gaworld.work.coordination import actual_final_conflict_free
from v0_first_batch.schema import CriterionResult, GateResult, compose


def first_error(*, track: str, variant: str, loop: dict[str, Any], want: dict[str, Any], private: dict[str, dict[str, Any]]) -> str:
    report_errors = loop.get("report_errors") or {}
    if report_errors.get("agent_a") != "ok" or report_errors.get("agent_b") != "ok":
        return "private_constraint_not_reported"
    if not (loop.get("reports") or {}).get("agent_a") or not (loop.get("reports") or {}).get("agent_b"):
        return "private_constraint_not_reported"
    if track == "drop_revision" and variant == "intervention":
        return "constraint_revision_not_delivered"
    if track == "multi" and variant == "intervention" and not loop.get("revision_delivered"):
        return "constraint_revision_not_delivered"
    if track == "drop_coordinator" or (track == "multi" and not loop.get("plan_delivered")):
        if track == "drop_coordinator" or not loop.get("plan_delivered"):
            return "plan_not_delivered"
    violations = list(loop.get("violations") or [])
    naive = loop.get("naive") or {}
    if variant == "intervention" and track == "multi" and naive.get("agent_a") == naive.get("agent_b") and not violations:
        return "conflict_not_detected"
    plan = loop.get("plan") or {}
    if loop.get("plan_error") != "ok":
        return "invalid_joint_assignment"
    assignments = plan.get("assignments") or {}
    if variant == "intervention" and track == "multi" and violations and assignments == naive:
        return "joint_plan_not_revised"
    if assignments.get("agent_a") != want["assignments"]["agent_a"] or assignments.get("agent_b") != want["assignments"]["agent_b"]:
        return "invalid_joint_assignment"
    commits = loop.get("commits") or {}
    commit_errors = loop.get("commit_errors") or {}
    if commit_errors.get("agent_a") != "ok" or commit_errors.get("agent_b") != "ok":
        return "agent_rejected_assignment"
    if any(not (commits.get(agent) or {}).get("confirm") for agent in ("agent_a", "agent_b")):
        return "agent_rejected_assignment"
    versions = {str((commits.get(agent) or {}).get("plan_version") or "") for agent in ("agent_a", "agent_b")}
    if versions != {PLAN_VERSION}:
        return "plan_version_inconsistent"
    world = loop.get("world") or {}
    by_agent = world.get("by_agent") or {}
    for agent in ("agent_a", "agent_b"):
        if by_agent.get(agent) != assignments.get(agent):
            return "execution_deviated_from_plan"
        if by_agent.get(agent) not in set(private[agent]["feasible"]):
            return "execution_deviated_from_plan"
    if world.get("duplicates") or not actual_final_conflict_free(by_agent):
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
    actual_free = actual_final_conflict_free(by_agent) if by_agent else False
    joint_sat = all(by_agent.get(agent) in set(private[agent]["feasible"]) for agent in ("agent_a", "agent_b")) and len(by_agent) == 2
    committed = (
        loop.get("plan_error") == "ok"
        and assignments == want["assignments"]
        and (
            track == "direct"
            or (
                all((commits.get(agent) or {}).get("confirm") for agent in ("agent_a", "agent_b"))
                and {str((commits.get(agent) or {}).get("plan_version") or "") for agent in ("agent_a", "agent_b")} == {PLAN_VERSION}
            )
        )
    )
    matches = by_agent == want["assignments"] if track == "direct" else by_agent == assignments == want["assignments"]
    role_ok = bool(loop.get("a_ran")) and bool(loop.get("b_ran")) and bool(loop.get("coordinator_ran"))
    repair_ok = True
    if variant == "intervention" and track == "multi":
        repair_ok = bool(loop.get("violations")) and actual_free and matches
    elif track in {"drop_revision", "drop_coordinator"} and variant == "intervention":
        repair_ok = False
    detected = plan.get("initial_conflict_detected")
    self_ok = None if not isinstance(detected, bool) else detected is bool(want.get("initial_conflict"))
    extractable = (loop.get("plan_error") == "ok") if track == "direct" else all(
        [
            (loop.get("report_errors") or {}).get("agent_a") == "ok",
            (loop.get("report_errors") or {}).get("agent_b") == "ok",
            (loop.get("revision_error") == "ok"),
            (loop.get("initial_error") == "ok"),
            (loop.get("plan_error") == "ok"),
            (loop.get("commit_errors") or {}).get("agent_a") == "ok",
            (loop.get("commit_errors") or {}).get("agent_b") == "ok",
        ]
    )
    drop_ok = bool(loop.get("drop_revision_isolated", True)) and bool(loop.get("drop_coordinator_isolated", True))
    if track == "direct":
        drop_ok = True
    r0 = (
        bool(loop.get("budget_valid"))
        and extractable
        and bool(loop.get("peek_denied"))
        and bool(loop.get("env_denied"))
        and bool(loop.get("coordinator_exec_denied", True))
        and not loop.get("oracle_in_prompt")
        and not loop.get("leaks")
        and role_ok
        and drop_ok
        and int(loop.get("unregistered_modification") or 0) == 0
    )
    expect_success = track in {"multi", "direct"} or (track == "drop_revision" and variant == "control")
    conditioned = bool(r0 and expect_success and actual_free and joint_sat and committed and matches and repair_ok)
    if track == "drop_revision" and variant == "intervention":
        conditioned = False
    if track == "drop_coordinator":
        conditioned = False
    err = first_error(track=track, variant=variant, loop=loop, want=want, private=private)
    if track == "direct":
        if not r0:
            err = "none"
        elif loop.get("plan_error") != "ok":
            err = "invalid_joint_assignment"
        elif assignments != want["assignments"]:
            err = "invalid_joint_assignment"
        elif not actual_free:
            err = "final_state_conflict"
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
            GateResult("roles_ran", role_ok, layer="R0"),
            GateResult("drop_isolated", drop_ok, layer="R0"),
            GateResult("oracle_not_in_prompts", not loop.get("oracle_in_prompt"), layer="R0"),
            GateResult("environment_did_not_rewrite", bool(loop.get("env_denied")), layer="R0"),
            GateResult("coordinator_did_not_execute", bool(loop.get("coordinator_exec_denied", True)), layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[GateResult("world_exists", bool(world), layer="R1")],
        criteria=[
            CriterionResult("actual_final_conflict_free", "R2", "occupancy", True, 1.0 if actual_free else 0.0, passed=actual_free),
            CriterionResult("joint_constraint_satisfaction", "R2", "feasible_sets", True, 1.0 if joint_sat else 0.0, passed=joint_sat),
            CriterionResult("joint_plan_committed", "R2", "plan_version", True, 1.0 if committed else 0.0, passed=committed),
            CriterionResult("execution_matches_plan", "R2", "world_vs_plan", True, 1.0 if matches else 0.0, passed=matches),
            CriterionResult("role_completion", "R2", "roles", True, 1.0 if role_ok else 0.0, passed=role_ok),
            CriterionResult("conflict_repair_success", "R2", "repair", True, 1.0 if repair_ok else 0.0, passed=repair_ok),
            CriterionResult("oracle_conditioned_success", "R3", "joint_coordination", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "events": loop.get("events"), "budget": loop.get("budget"), "world": world, "violations": loop.get("violations")},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": track,
            "repeat_id": repeat_id,
            "actual_final_conflict_free": actual_free,
            "joint_constraint_satisfaction": joint_sat,
            "joint_plan_committed": committed,
            "execution_matches_plan": matches,
            "role_completion": role_ok,
            "conflict_repair_success": repair_ok,
            "self_assessment_correct": self_ok,
            "assessment_execution_gap": None if self_ok is None else int(not self_ok),
            "revision_delivered": bool(loop.get("revision_delivered")),
            "plan_delivered": bool(loop.get("plan_delivered")),
            "b_ran": bool(loop.get("b_ran")),
            "budget_calls": (loop.get("budget") or {}).get("calls"),
            "budget_kinds": (loop.get("budget") or {}).get("kinds"),
            "first_error": err,
            "got": by_agent,
            "want": want["assignments"],
            "ranking_note": "C1-02 multi-agent primary system, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell
