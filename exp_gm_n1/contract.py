"""Exclusive DecisionMaker actions. Source/Relay have their own field sets."""

from __future__ import annotations

import json
import re
from typing import Any

KEEP = "keep_current_plan"
REVISE = "revise_plan"
ACTIONS = (KEEP, REVISE)
REVISION_KEYS = ("target", "value")
CONTRACT_KEEP_EXTRA = "keep_carries_revision_fields"
CONTRACT_REVISE_MISSING = "revise_missing_revision_fields"
CONTRACT_ACTION = "action_not_in_contract"


def parse_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw)
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _present(payload: dict[str, Any], key: str) -> bool:
    if key not in payload:
        return False
    value = payload[key]
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def source_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    needed = ("source_id", "reported_state", "state_version")
    if any(not _present(payload, key) for key in needed):
        return dict(payload), "fields_not_extractable"
    return {key: payload[key] for key in needed}, "ok"


def relay_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    needed = ("verified_state", "source_id", "state_version")
    if any(not _present(payload, key) for key in needed):
        return dict(payload), "fields_not_extractable"
    return {key: payload[key] for key in needed}, "ok"


def decision_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if "action" not in payload or "evidence_message_id" not in payload:
        return dict(payload), "fields_not_extractable"
    name = payload.get("action")
    if name not in ACTIONS:
        return {k: payload.get(k) for k in ("action", "evidence_message_id", "target", "value") if k in payload}, CONTRACT_ACTION
    if name == KEEP:
        action = {"action": KEEP, "evidence_message_id": payload["evidence_message_id"]}
        if any(key in payload for key in REVISION_KEYS):
            action.update({key: payload.get(key) for key in REVISION_KEYS if key in payload})
            return action, CONTRACT_KEEP_EXTRA
        return action, "ok"
    missing = [key for key in ("action", "target", "value", "evidence_message_id") if not _present(payload, key)]
    action = {key: payload.get(key) for key in ("action", "target", "value", "evidence_message_id")}
    if missing:
        return action, CONTRACT_REVISE_MISSING
    return {
        "action": REVISE,
        "target": payload["target"],
        "value": payload["value"],
        "evidence_message_id": payload["evidence_message_id"],
    }, "ok"


def is_contract_failure(reason: str) -> bool:
    return reason in {CONTRACT_KEEP_EXTRA, CONTRACT_REVISE_MISSING, CONTRACT_ACTION}
