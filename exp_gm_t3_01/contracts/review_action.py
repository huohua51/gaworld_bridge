"""Exclusive reviewer actions. No decision/mismatches/required_change blob."""

from __future__ import annotations

import json
import re
from typing import Any

APPROVE = "approve_draft"
REVISE = "request_revision"
ACTIONS = (APPROVE, REVISE)
REVISION_KEYS = ("target", "required_value")
CONTRACT_APPROVE_EXTRA = "approve_carries_revision_fields"
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


def action_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if "action" not in payload or "evidence_id" not in payload:
        return dict(payload), "fields_not_extractable"
    name = payload.get("action")
    if name not in ACTIONS:
        return {k: payload.get(k) for k in ("action", "evidence_id", "target", "required_value") if k in payload}, CONTRACT_ACTION
    if name == APPROVE:
        action = {"action": APPROVE, "evidence_id": payload["evidence_id"]}
        if any(key in payload for key in REVISION_KEYS):
            extra = {key: payload.get(key) for key in REVISION_KEYS if key in payload}
            action.update(extra)
            return action, CONTRACT_APPROVE_EXTRA
        return action, "ok"
    missing = [key for key in ("action", "target", "required_value", "evidence_id") if not _present(payload, key)]
    action = {key: payload.get(key) for key in ("action", "target", "required_value", "evidence_id")}
    if missing:
        return action, CONTRACT_REVISE_MISSING
    return {
        "action": REVISE,
        "target": payload["target"],
        "required_value": payload["required_value"],
        "evidence_id": payload["evidence_id"],
    }, "ok"


def is_contract_failure(reason: str) -> bool:
    return reason in {CONTRACT_APPROVE_EXTRA, CONTRACT_REVISE_MISSING, CONTRACT_ACTION}


def to_channel_payload(action: dict[str, Any], *, task: dict[str, Any], private: dict[str, Any], draft_version: str) -> dict[str, Any]:
    if action.get("action") == APPROVE:
        return {
            "decision": "approve",
            "reviewed_spec_version": draft_version,
            "required_spec_version": str(private.get("spec_version") or draft_version),
            "criterion_id": str(task["criterion_id"]),
            "evidence": str(action.get("evidence_id") or ""),
            "required_change": {},
        }
    return {
        "decision": "revise",
        "reviewed_spec_version": draft_version,
        "required_spec_version": str(private.get("spec_version") or "v2"),
        "criterion_id": str(task["criterion_id"]),
        "evidence": str(action.get("evidence_id") or ""),
        "required_change": {str(action.get("target")): action.get("required_value")},
    }
