"""R0—R3 and first_error for TASK-I1."""

from __future__ import annotations

from typing import Any


def first_error(
    *,
    track: str,
    events: list[str],
    observation_ok: bool,
    raw_sent: bool,
    raw_delivered: bool,
    verification_requested: bool,
    wrong_source: bool,
    verified_emitted: bool,
    verified_delivered: bool,
    verified_read: bool,
    verified_adopted: bool,
    unauthorized_read: bool,
    target_correct: bool,
    stale: bool,
    contract_error: str = "ok",
) -> str:
    if unauthorized_read:
        return "unauthorized_private_read"
    if track != "focused" and not observation_ok:
        return "observation_not_created"
    if track != "focused" and not raw_sent:
        return "raw_signal_not_sent"
    if track in {"full", "drop_verified"} and not raw_delivered:
        return "raw_signal_not_delivered"
    if track in {"full", "drop_verified"} and not verification_requested:
        return "verification_not_requested"
    if wrong_source:
        return "wrong_source_verified"
    if track in {"full", "drop_verified"} and not verified_emitted:
        return "verified_message_not_emitted"
    if track == "full" and not verified_delivered:
        return "verified_message_not_delivered"
    if track in {"focused", "full"} and not verified_read:
        return "verified_message_not_read"
    if track in {"focused", "full"} and not verified_adopted:
        return "verified_state_not_adopted"
    if stale:
        return "stale_state_used"
    if track in {"focused", "full"} and contract_error not in {"ok", "empty"}:
        return contract_error
    if not target_correct:
        return "target_action_incorrect"
    return "none"
    if unauthorized_read:
        return "unauthorized_private_read"
    if track != "focused" and not observation_ok:
        return "observation_not_created"
    if track != "focused" and not raw_sent:
        return "raw_signal_not_sent"
    if track in {"full", "drop_verified"} and not raw_delivered:
        return "raw_signal_not_delivered"
    if track in {"full", "drop_verified"} and not verification_requested:
        return "verification_not_requested"
    if wrong_source:
        return "wrong_source_verified"
    if track in {"full", "drop_verified"} and not verified_emitted:
        return "verified_message_not_emitted"
    if track == "full" and not verified_delivered:
        return "verified_message_not_delivered"
    if track in {"focused", "full"} and not verified_read:
        return "verified_message_not_read"
    if track in {"focused", "full"} and not verified_adopted:
        return "verified_state_not_adopted"
    if stale:
        return "stale_state_used"
    if not target_correct:
        return "target_action_incorrect"
    return "none"


def r0_ok(track: str, loop: dict[str, Any]) -> tuple[bool, str]:
    if loop.get("dispatcher_read_trust"):
        return False, "dispatcher read verifier trust table"
    if loop.get("verifier_submitted"):
        return False, "verifier submitted an action"
    if track == "drop_verified" and not loop.get("inbox_empty"):
        return False, "drop-verified inbox was not empty"
    if track == "drop_verified" and loop.get("leak_on_drop"):
        return False, f"verified/trust leaked into drop: {loop['leak_on_drop']}"
    if track == "full" and "verified_message_emitted" in (loop.get("events") or []) and loop.get("inbox_empty"):
        return False, "full-track verified not delivered"
    if track == "focused" and loop.get("observer_calls"):
        return False, "focused called observer"
    if track in {"full", "drop_verified"} and loop.get("verifier_calls") != 1:
        return False, f"verifier calls={loop.get('verifier_calls')}"
    if track == "no_verification" and loop.get("verifier_calls"):
        return False, "no-verification called verifier"
    return True, "ok"


def process_success(track: str, loop: dict[str, Any], *, target_correct: bool, other_also: bool) -> bool:
    if not target_correct or other_also:
        return False
    action = loop.get("action") or {}
    verified = loop.get("verified") or {}
    if track in {"drop_verified", "no_verification"}:
        return False
    if loop.get("contract_error") not in {None, "ok"}:
        return False
    if action.get("evidence_message_id") != verified.get("message_id"):
        return False
    if action.get("adopted_state_version") != loop.get("expected_version"):
        return False
    adopted = loop.get("adopt") or {}
    return bool(adopted.get("ok") or adopted.get("reason") == "verified_already_adopted")
