"""L1-01 scoring. World events, not self-report."""

from __future__ import annotations

from typing import Any

from exp_gm_l1_01b.contract import CHECKPOINT_VERSION, EXTRACTABLE_STEP_ERRORS
from exp_gm_l1_01b.loader import oracle_plan, solve_outputs
from v0_first_batch.schema import CriterionResult, GateResult, compose


def _world_outputs(world: dict[str, Any]) -> dict[str, Any]:
    steps = world.get("steps") or {}
    return {sid: dict((body or {}).get("output") or {}) for sid, body in steps.items()}


def _world_actors(world: dict[str, Any]) -> dict[str, str]:
    steps = world.get("steps") or {}
    return {sid: str((body or {}).get("actor") or "") for sid, body in steps.items()}


def _consume_error(task: dict[str, Any], outputs: dict[str, Any], want_out: dict[str, Any]) -> str | None:
    if task.get("kind") != "receive_verify_archive":
        return None
    recv_ids = list((want_out.get(task["step_ids"][0]) or {}).get("received_ids") or [])
    got_v = outputs.get(task["step_ids"][1]) or {}
    verified = list(got_v.get("verified_ids") or [])
    if any(item not in set(recv_ids) for item in verified):
        return "invented_ids"
    if verified != recv_ids:
        return "completed_stage_output_not_consumed"
    return None


def first_error(*, track: str, variant: str, loop: dict[str, Any], want: dict[str, Any], task: dict[str, Any]) -> str:
    if loop.get("step1_error") not in EXTRACTABLE_STEP_ERRORS or loop.get("checkpoint_error") not in {"ok"}:
        if not loop.get("checkpoint_created"):
            return "checkpoint_not_created"
    if track == "drop_checkpoint" and variant == "intervention":
        return "checkpoint_not_delivered"
    if track == "drop_handoff" and variant == "intervention":
        return "handoff_not_delivered"
    if not loop.get("checkpoint_created"):
        return "checkpoint_not_created"
    if variant == "intervention" and track == "multi" and not loop.get("checkpoint_delivered_successor"):
        return "checkpoint_not_delivered"
    if variant == "intervention" and track == "multi" and not loop.get("handoff_completed"):
        return "handoff_not_delivered"
    used = str(loop.get("checkpoint_version_used") or "")
    if loop.get("resume_error") == "ok" and used and used != CHECKPOINT_VERSION:
        return "stale_checkpoint_used"
    declared = str(loop.get("resume_declared") or "")
    expected_resume = str(want.get("resume_step") or task["step_ids"][1])
    if variant == "intervention" and track == "multi" and declared != expected_resume:
        return "resume_from_wrong_step"
    if loop.get("duplicates"):
        return "duplicate_action"
    if not loop.get("completed_work_preserved", True):
        return "completed_work_overwritten"
    world = loop.get("world") or {}
    completed = list(world.get("completed_steps") or [])
    if any(step_id not in completed for step_id in task["step_ids"]):
        if declared and declared != expected_resume:
            return "resume_from_wrong_step"
        if len(completed) < len(task["step_ids"]) and completed:
            return "remaining_step_skipped"
        return "workflow_not_completed"
    outputs = _world_outputs(world)
    want_out = want["outputs"]
    consumed = _consume_error(task, outputs, want_out)
    if consumed:
        return consumed
    if outputs != want_out:
        return "workflow_not_completed"
    actors = _world_actors(world)
    if track != "direct" and actors != want["actor_by_step"]:
        return "workflow_not_completed"
    if not loop.get("env_denied"):
        return "environment_fallback"
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
    world = loop.get("world") or {}
    outputs = _world_outputs(world)
    actors = _world_actors(world)
    want_out = want["outputs"] if track != "direct" else solve_outputs(task)
    created = bool(loop.get("checkpoint_created")) if track != "direct" else True
    delivered = True if track == "direct" or variant == "control" else bool(loop.get("checkpoint_delivered_successor"))
    if track == "drop_checkpoint" and variant == "intervention":
        delivered = False
    resume_ok = True if track == "direct" else str(loop.get("resume_declared") or "") == str(want.get("resume_step") or "")
    if variant == "control" and track != "direct":
        resume_ok = str(loop.get("resume_declared") or "") == str(want.get("resume_step") or "")
    preserved = bool(loop.get("completed_work_preserved", True))
    dup_rate = 1.0 if loop.get("duplicates") else 0.0
    handoff_ok = True if track == "direct" else bool(loop.get("handoff_completed"))
    if track == "drop_handoff" and variant == "intervention":
        handoff_ok = False
    complete = outputs == want_out and list(world.get("completed_steps") or []) == list(task["step_ids"])
    if track != "direct":
        complete = complete and actors == want["actor_by_step"]
    extractable = True
    if track == "direct":
        extractable = loop.get("direct_error") == "ok"
    else:
        extractable = all(
            [
                loop.get("step1_error") in EXTRACTABLE_STEP_ERRORS,
                loop.get("checkpoint_error") == "ok",
                loop.get("handoff_error") in EXTRACTABLE_STEP_ERRORS | {"ok"},
                loop.get("resume_error") in EXTRACTABLE_STEP_ERRORS,
                loop.get("step2_error") in EXTRACTABLE_STEP_ERRORS,
                loop.get("step3_error") in EXTRACTABLE_STEP_ERRORS,
            ]
        )
    role_ok = bool(loop.get("a_ran")) and bool(loop.get("coordinator_ran"))
    if variant == "intervention" and track != "direct":
        role_ok = role_ok and bool(loop.get("b_ran"))
    drop_ok = bool(loop.get("drop_checkpoint_isolated", True)) and bool(loop.get("drop_handoff_isolated", True))
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
    )
    expect_success = track in {"multi", "direct"} or (track in {"drop_checkpoint", "drop_handoff"} and variant == "control")
    version_ok = track == "direct" or str(loop.get("checkpoint_version_used") or "") in {"", CHECKPOINT_VERSION}
    if track == "multi" and variant == "intervention":
        version_ok = str(loop.get("checkpoint_version_used") or "") == CHECKPOINT_VERSION
    conditioned = bool(r0 and expect_success and complete and created and preserved and dup_rate == 0.0 and version_ok)
    if track == "multi":
        conditioned = bool(conditioned and resume_ok and handoff_ok and delivered)
    if track == "drop_checkpoint" and variant == "intervention":
        conditioned = False
    if track == "drop_handoff" and variant == "intervention":
        conditioned = False
    err = first_error(track=track, variant=variant, loop=loop, want=want, task=task)
    if track == "direct":
        if not r0:
            err = "none"
        elif loop.get("direct_error") != "ok":
            err = "workflow_not_completed"
        else:
            err = _consume_error(task, outputs, want_out) or ("none" if complete else "workflow_not_completed")
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
            CriterionResult("checkpoint_created", "R2", "checkpoint", True, 1.0 if created else 0.0, passed=created),
            CriterionResult("checkpoint_delivered", "R2", "checkpoint", True, 1.0 if delivered else 0.0, passed=delivered),
            CriterionResult("resume_position_correct", "R2", "resume", True, 1.0 if resume_ok else 0.0, passed=resume_ok),
            CriterionResult("completed_work_preserved", "R2", "preserve", True, 1.0 if preserved else 0.0, passed=preserved),
            CriterionResult("duplicate_action_rate", "R2", "duplicate", True, dup_rate, passed=dup_rate == 0.0),
            CriterionResult("handoff_completed", "R2", "handoff", True, 1.0 if handoff_ok else 0.0, passed=handoff_ok),
            CriterionResult("workflow_complete", "R2", "world", True, 1.0 if complete else 0.0, passed=complete),
            CriterionResult("oracle_conditioned_success", "R3", "handoff_recovery", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "events": loop.get("events"), "budget": loop.get("budget"), "world": world},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": track,
            "repeat_id": repeat_id,
            "checkpoint_created": created,
            "checkpoint_delivered": delivered,
            "resume_position_correct": resume_ok,
            "completed_work_preserved": preserved,
            "duplicate_action_rate": dup_rate,
            "handoff_completed": handoff_ok,
            "workflow_complete": complete,
            "recovery_latency": loop.get("recovery_latency"),
            "role_completion": role_ok,
            "b_ran": bool(loop.get("b_ran")),
            "budget_calls": (loop.get("budget") or {}).get("calls"),
            "drop_checkpoint_isolated": bool(loop.get("drop_checkpoint_isolated", True)),
            "drop_handoff_isolated": bool(loop.get("drop_handoff_isolated", True)),
            "first_error": err,
            "got_outputs": outputs,
            "want_outputs": want_out,
            "got_actors": actors,
            "want_actors": want.get("actor_by_step"),
            "ranking_note": "L1-01b interruption recovery, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell
