"""R0—R3 and first_error for EXP-GM-01."""

from __future__ import annotations

from typing import Any

from v0_first_batch.schema import CriterionResult, GateResult, compose


FIRST_ERRORS = (
    "event_not_injected",
    "wrong_state_version",
    "fields_not_extractable",
    "track_misconfigured",
    "action_not_submitted_by_agent",
    "environment_rewrote_schedule",
    "destination_closed",
    "type_mismatch",
    "unreachable",
    "schedule_conflict",
    "old_schedule_not_overwritten",
    "event_not_delivered",
    "event_not_adopted",
    "stale_state_used",
    "target_action_incorrect",
    "none",
)


def r0_ok(track: str, loop: dict[str, Any]) -> tuple[bool, str]:
    injected = loop.get("injected") or {}
    events = loop.get("events") or []
    if "event_injected" not in events or not injected:
        return False, "event_not_injected"
    if injected.get("state_version") != loop.get("expected_version"):
        return False, "wrong_state_version"
    if loop.get("contract_error") in {"fields_not_extractable", "empty"}:
        return False, "fields_not_extractable"
    if track == "direct_current_state":
        if "current_state_seeded" not in events:
            return False, "track_misconfigured"
        if "perception_packaged" in events or "perception_dropped" in events:
            return False, "track_misconfigured"
    elif track == "full_event":
        if "perception_packaged" not in events or "perception_delivered" not in events:
            return False, "track_misconfigured"
        if loop.get("inbox_empty"):
            return False, "track_misconfigured"
    elif track == "drop_event":
        if "perception_packaged" not in events or "perception_dropped" not in events:
            return False, "track_misconfigured"
        if not loop.get("inbox_empty"):
            return False, "track_misconfigured"
        if loop.get("leak_on_drop"):
            return False, f"event leaked into drop: {loop['leak_on_drop']}"
    else:
        return False, "track_misconfigured"
    return True, "ok"


def first_error(*, track: str, variant: str, loop: dict[str, Any], r0_detail: str, r2: dict[str, bool], r3: dict[str, bool], target_correct: bool) -> str:
    if r0_detail != "ok":
        if r0_detail in FIRST_ERRORS:
            return r0_detail
        if r0_detail.startswith("event leaked"):
            return "track_misconfigured"
        return "track_misconfigured"
    if loop.get("env_rewrote"):
        return "environment_rewrote_schedule"
    if "action_submitted" not in (loop.get("events") or []):
        return "action_not_submitted_by_agent"
    if loop.get("contract_error") not in {None, "ok", "empty"}:
        return str(loop.get("contract_error"))
    if not r2.get("destination_open"):
        return "destination_closed"
    if not r2.get("type_match"):
        return "type_mismatch"
    if not r2.get("reachable"):
        return "unreachable"
    if not r2.get("no_conflict"):
        return "schedule_conflict"
    if not r2.get("overwritten"):
        return "old_schedule_not_overwritten"
    if not target_correct:
        return "target_action_incorrect"
    if not r3.get("delivered"):
        return "event_not_delivered"
    if track != "drop_event" and not r3.get("adopted"):
        return "event_not_adopted"
    if r3.get("stale"):
        return "stale_state_used"
    return "none"


def process_success(track: str, *, target_correct: bool, r3: dict[str, bool]) -> bool:
    if not target_correct:
        return False
    if track == "drop_event":
        return False
    return bool(r3.get("delivered") and r3.get("adopted") and r3.get("overwritten") and not r3.get("stale"))


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
    dest = str(action.get("destination") or "")
    known = {probe["original"], probe["alternative"], probe["distractor"]}
    r2 = {
        "destination_open": bool(dest) and dest in known and channel.destination_open(task_id, dest),
        "type_match": bool(dest) and channel.type_match(task_id, dest),
        "reachable": bool(dest) and channel.reachable(task_id, dest),
        "no_conflict": not channel.schedule_conflict(task_id),
        "overwritten": channel.old_schedule_overwritten(
            task_id, probe["original"], must_change=bool(loop["spec"]["must_change_slot"])
        ),
    }
    follow = channel.slot_of(task_id, probe["follow_slot_id"]) or {}
    if follow.get("destination") != probe["follow_destination"]:
        r2["no_conflict"] = False
    r0, r0_detail = r0_ok(track, loop)
    notice = loop.get("notice") or {}
    injected = loop.get("injected") or {}
    r3 = {
        "delivered": (not loop.get("inbox_empty")) if track != "drop_event" else False,
        "adopted": bool(
            action.get("evidence_event_id")
            and action.get("evidence_event_id") == injected.get("event_id")
            and loop.get("adopt")
            and (loop["adopt"].get("ok") or loop["adopt"].get("reason") == "event_already_adopted")
        ),
        "overwritten": r2["overwritten"],
        "stale": bool(action.get("adopted_state_version") not in {None, "", loop.get("expected_version")}) and track != "drop_event",
    }
    target_correct = dest == loop.get("oracle_destination") and all(
        (r2["destination_open"], r2["type_match"], r2["reachable"], r2["no_conflict"], r2["overwritten"])
    )
    other_also = dest == (probe["alternative"] if variant == "control" else probe["original"])
    conditioned = process_success(track, target_correct=target_correct, r3=r3)
    err = first_error(track=track, variant=variant, loop=loop, r0_detail=r0_detail, r2=r2, r3=r3, target_correct=target_correct)
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("event_injected", "event_injected" in (loop.get("events") or []) and bool(injected), layer="R0"),
            GateResult("version_correct", injected.get("state_version") == loop.get("expected_version"), layer="R0"),
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("tracks_consistent", r0_detail == "ok" or r0_detail != "track_misconfigured", layer="R0", detail=r0_detail),
            GateResult("r0_ok", r0, layer="R0", detail=r0_detail),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult("action_submitted_by_agent", "action_submitted" in (loop.get("events") or []) and not loop.get("env_submitted"), layer="R1"),
            GateResult("schedule_not_rewritten_by_env", not loop.get("env_rewrote"), layer="R1"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="visit_oracle",
                evaluable=True,
                score=1.0 if target_correct else 0.0,
                passed=target_correct,
                critical=False,
                detail=f"got={dest} oracle={loop.get('oracle_destination')} r2={r2}",
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="event_bind",
                evaluable=True,
                score=1.0 if conditioned else 0.0,
                passed=conditioned,
                critical=True,
                detail=f"evidence={action.get('evidence_event_id')} version={action.get('adopted_state_version')} r3={r3}",
            ),
        ],
        process_profile={
            "first_error": err,
            "events": loop.get("events"),
            "agent_calls": loop.get("agent_calls"),
            "r2": r2,
            "r3": r3,
            "notice_event_id": notice.get("event_id"),
            "injected_event_id": injected.get("event_id"),
        },
        extra={
            "probe_id": probe["id"],
            "track": track,
            "variant": variant,
            "seed": seed,
            "target_correct": target_correct,
            "oracle_conditioned_success": conditioned,
            "other_also": other_also,
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


def closure_adaptation_rate(cells: list[dict], track: str) -> float | None:
    """P(legal alternative + schedule update | venue actually closed)."""
    return _variant_mean(cells, track, "intervention", "target_correct")


def control_stability_rate(cells: list[dict], track: str) -> float | None:
    """P(keep original destination | venue still open)."""
    return _variant_mean(cells, track, "control", "target_correct")


def unnecessary_replan_rate(cells: list[dict], track: str) -> float | None:
    stability = control_stability_rate(cells, track)
    if stability is None:
        return None
    return round(1.0 - stability, 4)
