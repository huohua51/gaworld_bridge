"""keep/update exclusive contract with evidence binding."""

from __future__ import annotations

import json
import re
from typing import Any

KEEP = "keep"
UPDATE = "update"
DECISIONS = (KEEP, UPDATE)
EVIDENCE_KEYS = ("path", "observed", "required")
CHANGE_KEYS = ("path", "old_value", "new_value")
CONTRACT_KEEP_EXTRA = "keep_carries_required_change"
CONTRACT_UPDATE_MISSING = "update_missing_required_change"
CONTRACT_ACTION = "decision_not_in_contract"


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


def _evidence_ok(evidence: Any) -> bool:
    if not isinstance(evidence, dict):
        return False
    return all(key in evidence for key in EVIDENCE_KEYS)


def _change_ok(change: Any) -> bool:
    if not isinstance(change, dict):
        return False
    return all(_present(change, key) for key in CHANGE_KEYS)


def action_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if "decision" not in payload or "evidence" not in payload or "required_change" not in payload:
        return dict(payload), "fields_not_extractable"
    if not _evidence_ok(payload.get("evidence")):
        return dict(payload), "fields_not_extractable"
    name = payload.get("decision")
    if name not in DECISIONS:
        return dict(payload), CONTRACT_ACTION
    evidence = {key: payload["evidence"].get(key) for key in EVIDENCE_KEYS}
    if name == KEEP:
        if payload.get("required_change") is not None:
            return {"decision": KEEP, "evidence": evidence, "required_change": payload.get("required_change")}, CONTRACT_KEEP_EXTRA
        return {"decision": KEEP, "evidence": evidence, "required_change": None}, "ok"
    if not _change_ok(payload.get("required_change")):
        return {"decision": UPDATE, "evidence": evidence, "required_change": payload.get("required_change")}, CONTRACT_UPDATE_MISSING
    change = {key: payload["required_change"][key] for key in CHANGE_KEYS}
    return {"decision": UPDATE, "evidence": evidence, "required_change": change}, "ok"
