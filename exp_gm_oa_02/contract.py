"""Conditional schema: keep has no revision fields; revise must have them."""

from __future__ import annotations

from typing import Any

KEEP = "keep_current_plan"
REVISE = "revise_plan"
ACTIONS = (KEEP, REVISE)
KEEP_KEYS = ("action", "evidence_event_id")
REVISE_KEYS = ("action", "target", "value", "evidence_event_id")
REVISION_KEYS = ("target", "value")
CONTRACT_KEEP_EXTRA = "keep_carries_revision_fields"
CONTRACT_REVISE_MISSING = "revise_missing_revision_fields"
CONTRACT_ACTION = "action_not_in_contract"


def _present(payload: dict[str, Any], key: str) -> bool:
    if key not in payload:
        return False
    value = payload[key]
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def action_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if "action" not in payload or "evidence_event_id" not in payload:
        return dict(payload), "fields_not_extractable"
    name = payload.get("action")
    if name not in ACTIONS:
        action = {key: payload.get(key) for key in ("action", "evidence_event_id", "target", "value") if key in payload}
        return action, CONTRACT_ACTION
    if name == KEEP:
        action = {key: payload[key] for key in KEEP_KEYS}
        if any(key in payload for key in REVISION_KEYS):
            extra = {key: payload.get(key) for key in REVISION_KEYS if key in payload}
            action.update(extra)
            return action, CONTRACT_KEEP_EXTRA
        return action, "ok"
    missing = [key for key in REVISE_KEYS if not _present(payload, key)]
    action = {key: payload.get(key) for key in REVISE_KEYS}
    if missing:
        return action, CONTRACT_REVISE_MISSING
    return {"action": REVISE, "target": payload["target"], "value": payload["value"], "evidence_event_id": payload["evidence_event_id"]}, "ok"


def is_contract_failure(reason: str) -> bool:
    return reason in {CONTRACT_KEEP_EXTRA, CONTRACT_REVISE_MISSING, CONTRACT_ACTION}
