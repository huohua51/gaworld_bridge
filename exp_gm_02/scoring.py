"""R0—R3 and first_error for EXP-GM-02."""

from __future__ import annotations

from typing import Any

from gaworld.life.family import NONE
from v0_first_batch.schema import CriterionResult, GateResult, compose


FIRST_ERRORS = (
    "care_event_not_injected",
    "care_event_not_delivered",
    "stale_family_state_used",
    "wrong_caregiver_selected",
    "responsibility_not_accepted",
    "control_false_positive_care",
    "conflicting_schedule_not_updated",
    "incorrect_expense",
    "duplicate_expense",
    "environment_assigned_caregiver",
    "fields_not_extractable",
    "track_misconfigured",
    "none",
)


def r0_ok(track: str, loop: dict[str, Any]) -> tuple[bool, str]:
    injected = loop.get("injected") or {}
    events = loop.get("events") or []
    if "care_event_injected" not in events or not injected:
        return False, "care_event_not_injected"
    if injected.get("state_version") != loop.get("expected_version"):
        return False, "stale_family_state_used"
    if loop.get("contract_error") in {"fields_not_extractable", "empty"}:
        return False, "fields_not_extractable"
    if track == "direct_household_state":
        if "current_state_seeded" not in events:
            return False, "track_misconfigured"
        if "perception_packaged" in events or "perception_dropped" in events:
            return False, "track_misconfigured"
    elif track == "full_family_event":
        if "perception_packaged" not in events or "perception_delivered" not in events:
            return False, "track_misconfigured"
        if loop.get("inbox_empty"):
            return False, "track_misconfigured"
    elif track == "drop_family_event":
        if "perception_packaged" not in events or "perception_dropped" not in events:
            return False, "track_misconfigured"
        if not loop.get("inbox_empty"):
            return False, "track_misconfigured"
    else:
        return False, "track_misconfigured"
    return True, "ok"


def _control_ok(action: dict[str, Any], slot: dict[str, Any], expenses: list[dict[str, Any]]) -> bool:
    return (
        action.get("action") == "keep_schedule"
        and action.get("caregiver_id") == NONE
        and action.get("patient_id") == NONE
        and action.get("event_id") == NONE
        and action.get("schedule_decision") == "keep"
        and int(action.get("expense_amount") or 0) == 0
        and action.get("evidence_event_id") == NONE
        and action.get("adopted_state_version") == "v1"
        and slot.get("status") != "cancelled"
        and not expenses
    )


def _intervention_ok(
    *,
    probe: dict,
    action: dict[str, Any],
    slot: dict[str, Any],
    expenses: list[dict[str, Any]],
    injected: dict[str, Any],
    responsibility: str | None,
) -> bool:
    event_id = str(injected.get("event_id") or "")
    return (
        action.get("action") == "provide_care"
        and action.get("caregiver_id") == probe["legal_caregiver_id"]
        and action.get("patient_id") == probe["patient_id"]
        and action.get("event_id") == event_id
        and action.get("slot_id") == probe["conflict_slot_id"]
        and action.get("schedule_decision") == "cancel"
        and int(action.get("expense_amount") or 0) == int(probe["registered_expense"])
        and action.get("adopted_state_version") == "v2"
        and action.get("evidence_event_id") == event_id
        and slot.get("status") == "cancelled"
        and len(expenses) == 1
        and int((expenses[0] or {}).get("amount") or 0) == int(probe["registered_expense"])
        and responsibility == probe["legal_caregiver_id"]
    )


def first_error(*, variant: str, track: str, loop: dict[str, Any], r0_detail: str, action: dict[str, Any]) -> str:
    if r0_detail != "ok":
        if r0_detail in FIRST_ERRORS:
            return r0_detail
        return "track_misconfigured"
    if loop.get("env_assigned"):
        return "environment_assigned_caregiver"
    if "action_submitted" not in (loop.get("events") or []):
        return "fields_not_extractable"
    injected = loop.get("injected") or {}
    expenses = list(loop.get("expenses") or [])
    slot = {}
    channel = loop.get("channel")
    if channel is not None:
        slot = channel.slot_of(loop.get("task_id"), action.get("slot_id") or "") or {}
    if track == "drop_family_event" and variant == "intervention":
        return "care_event_not_delivered"
    if variant == "control":
        if action.get("action") == "provide_care" or action.get("caregiver_id") not in {NONE, "", None}:
            return "control_false_positive_care"
        if int(action.get("expense_amount") or 0) != 0 or expenses:
            return "incorrect_expense"
        if action.get("schedule_decision") != "keep" or slot.get("status") == "cancelled":
            return "conflicting_schedule_not_updated"
        if action.get("adopted_state_version") not in {None, "", "v1"}:
            return "stale_family_state_used"
        return "none"
    if action.get("caregiver_id") != (loop.get("spec") or {}).get("oracle_caregiver"):
        return "wrong_caregiver_selected"
    if action.get("action") != "provide_care" or not loop.get("responsibility"):
        return "responsibility_not_accepted"
    if slot.get("status") != "cancelled" or action.get("schedule_decision") != "cancel":
        return "conflicting_schedule_not_updated"
    if len(expenses) > 1:
        return "duplicate_expense"
    if int(action.get("expense_amount") or 0) != int((loop.get("spec") or {}).get("oracle_expense") or 0) or len(expenses) != 1:
        return "incorrect_expense"
    if track != "drop_family_event" and loop.get("inbox_empty"):
        return "care_event_not_delivered"
    if action.get("evidence_event_id") != injected.get("event_id") or action.get("adopted_state_version") != loop.get("expected_version"):
        return "stale_family_state_used"
    return "none"


def process_success(variant: str, track: str, *, target_correct: bool) -> bool:
    if not target_correct:
        return False
    if variant == "intervention" and track == "drop_family_event":
        return False
    return True


def score_cell(
    *,
    probe: dict,
    variant: str,
    track: str,
    seed: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    channel = loop["channel"]
    task_id = str(loop.get("task_id") or instance_id)
    action = loop.get("action") or {}
    injected = loop.get("injected") or {}
    expenses = channel.expenses_of(task_id)
    slot = channel.slot_of(task_id, probe["conflict_slot_id"]) or {}
    responsibility = channel.responsibility_of(task_id)
    r0, r0_detail = r0_ok(track, loop)
    if variant == "control":
        target_correct = _control_ok(action, slot, expenses)
    else:
        target_correct = _intervention_ok(
            probe=probe,
            action=action,
            slot=slot,
            expenses=expenses,
            injected=injected,
            responsibility=responsibility,
        )
    loop = dict(loop)
    loop["expenses"] = expenses
    loop["responsibility"] = responsibility
    conditioned = process_success(variant, track, target_correct=target_correct)
    err = first_error(variant=variant, track=track, loop=loop, r0_detail=r0_detail, action=action)
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("care_event_injected", "care_event_injected" in (loop.get("events") or []) and bool(injected), layer="R0"),
            GateResult("version_correct", injected.get("state_version") == loop.get("expected_version"), layer="R0"),
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("r0_ok", r0, layer="R0", detail=r0_detail),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult("action_submitted_by_agent", "action_submitted" in (loop.get("events") or []), layer="R1"),
            GateResult("environment_did_not_assign", not loop.get("env_assigned"), layer="R1"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="care_oracle",
                evaluable=True,
                score=1.0 if target_correct else 0.0,
                passed=target_correct,
                critical=False,
                detail=f"action={action.get('action')} caregiver={action.get('caregiver_id')} expense={action.get('expense_amount')} slot={slot.get('status')}",
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="care_bind",
                evaluable=True,
                score=1.0 if conditioned else 0.0,
                passed=conditioned,
                critical=True,
                detail=f"evidence={action.get('evidence_event_id')} version={action.get('adopted_state_version')}",
            ),
        ],
        process_profile={
            "first_error": err,
            "events": loop.get("events"),
            "agent_calls": loop.get("agent_calls"),
            "responsibility": responsibility,
            "expense_count": len(expenses),
            "slot_status": slot.get("status"),
            "injected_event_id": injected.get("event_id"),
        },
        extra={
            "probe_id": probe["id"],
            "track": track,
            "variant": variant,
            "seed": seed,
            "target_correct": target_correct,
            "oracle_conditioned_success": conditioned,
            "control_false_positive": variant == "control" and action.get("action") == "provide_care",
            "action": action,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell


def _variant_mean(cells: list[dict], track: str, variant: str, field: str) -> float | None:
    subset = [
        c for c in cells
        if (c.get("extra") or {}).get("track") == track
        and (c.get("extra") or {}).get("variant") == variant
        and c.get("measurement_valid")
    ]
    if not subset:
        return None
    if field == "target_correct":
        return round(sum(int(bool((c.get("extra") or {}).get("target_correct"))) for c in subset) / len(subset), 4)
    scored = [c for c in subset if c.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(c["full_pass"]) for c in scored) / len(scored), 4)


def care_adaptation_rate(cells: list[dict], track: str) -> float | None:
    return _variant_mean(cells, track, "intervention", "target_correct")


def control_stability_rate(cells: list[dict], track: str) -> float | None:
    return _variant_mean(cells, track, "control", "target_correct")


def unnecessary_replan_rate(cells: list[dict], track: str) -> float | None:
    stability = control_stability_rate(cells, track)
    if stability is None:
        return None
    return round(1.0 - stability, 4)
