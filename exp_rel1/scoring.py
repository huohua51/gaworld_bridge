"""R0—R3 and first_error for TASK-REL1."""

from __future__ import annotations

from typing import Any


def first_error(
    *,
    track: str,
    events: list[str],
    observation_ok: bool,
    current_sent: bool,
    current_delivered: bool,
    trust_requested: bool,
    history_read: bool,
    history_missing: bool,
    trust_emitted: bool,
    trust_delivered: bool,
    trust_read: bool,
    trust_adopted: bool,
    trust_updated: bool,
    unauthorized_read: bool,
    formation_correct: bool,
    update_correct: bool,
    stale: bool,
) -> str:
    if unauthorized_read:
        return "unauthorized_history_read"
    if track != "focused" and not observation_ok:
        return "observation_not_created"
    if track != "focused" and not current_sent:
        return "current_signal_not_sent"
    if track in {"full", "drop_trust"} and not current_delivered:
        return "current_signal_not_delivered"
    if track == "no_history" and history_missing:
        return "history_not_available"
    if track in {"full", "drop_trust"} and not trust_requested:
        return "trust_not_requested"
    if track in {"full", "drop_trust"} and not history_read:
        return "history_not_read"
    if track in {"full", "drop_trust"} and not trust_emitted:
        return "trust_message_not_emitted"
    if track == "full" and not trust_delivered:
        return "trust_message_not_delivered"
    if track in {"focused", "full"} and not trust_read:
        return "trust_message_not_read"
    if track in {"focused", "full"} and not trust_adopted:
        return "trust_state_not_adopted"
    if stale:
        return "stale_trust_used"
    if not formation_correct:
        return "formation_action_incorrect"
    if track in {"focused", "full"} and not trust_updated:
        return "trust_not_updated"
    if not update_correct:
        return "update_action_incorrect"
    return "none"


def r0_ok(track: str, loop: dict[str, Any]) -> tuple[bool, str]:
    if loop.get("dispatcher_read_history"):
        return False, "dispatcher read trust history"
    if loop.get("updater_submitted"):
        return False, "trust_updater submitted an action"
    if track == "drop_trust" and not loop.get("inbox_empty"):
        return False, "drop-trust inbox was not empty"
    if track == "drop_trust" and loop.get("leak_on_drop"):
        return False, f"history leaked into drop: {loop['leak_on_drop']}"
    if track == "full" and "trust_message_emitted" in (loop.get("events") or []) and loop.get("inbox_empty"):
        return False, "full-track trust not delivered"
    if track == "focused" and loop.get("observer_calls"):
        return False, "focused called observer"
    if track == "focused" and loop.get("updater_calls"):
        return False, "focused called trust_updater"
    if track in {"full", "drop_trust"} and loop.get("updater_calls") != 2:
        return False, f"updater calls={loop.get('updater_calls')}"
    if track == "no_history" and loop.get("updater_calls") != 2:
        return False, f"no-history updater calls={loop.get('updater_calls')}"
    return True, "ok"


def _bound(action: dict[str, Any], trust: dict[str, Any] | None, version: str) -> bool:
    if not action or not trust:
        return False
    if action.get("evidence_message_id") != trust.get("message_id"):
        return False
    if action.get("adopted_trust_version") != version:
        return False
    return True


def process_success(track: str, loop: dict[str, Any], *, formation_correct: bool, update_correct: bool, other_also: bool) -> bool:
    if not formation_correct or not update_correct or other_also:
        return False
    if track in {"drop_trust", "no_history"}:
        return False
    formation_ok = _bound(
        loop.get("formation_action") or {},
        loop.get("formation_trust"),
        str(loop.get("expected_formation_version") or "v1"),
    )
    update_ok = _bound(
        loop.get("update_action") or {},
        loop.get("update_trust"),
        str(loop.get("expected_update_version") or "v2"),
    )
    return formation_ok and update_ok
