"""Reports, initial/final plans, commits. No vague conflict field required."""

from __future__ import annotations

import json
import re
from typing import Any

PLAN_VERSION = "plan-001"
INITIAL_VERSION = "plan-init"
RULE_ID = "priority_keep_then_earliest_free"


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


def report_contract(payload: dict[str, Any] | None, *, agent_id: str) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if any(not _present(payload, key) for key in ("agent_id", "feasible", "preferred")):
        return dict(payload), "fields_not_extractable"
    if payload.get("agent_id") != agent_id:
        return dict(payload), "fields_not_extractable"
    feasible = payload.get("feasible")
    if not isinstance(feasible, list) or not feasible or not all(isinstance(item, str) and item.strip() for item in feasible):
        return dict(payload), "fields_not_extractable"
    return {"agent_id": agent_id, "feasible": [str(item) for item in feasible], "preferred": str(payload["preferred"])}, "ok"


def plan_contract(payload: dict[str, Any] | None, *, version: str | None = None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if any(key not in payload for key in ("plan_version", "assignments", "rule")):
        return dict(payload), "fields_not_extractable"
    assignments = payload.get("assignments")
    if not isinstance(assignments, dict):
        return dict(payload), "fields_not_extractable"
    cleaned = {
        "plan_version": str(payload.get("plan_version") or ""),
        "assignments": {str(key): str(value) for key, value in assignments.items() if value is not None and str(value).strip()},
        "rule": str(payload.get("rule") or ""),
    }
    detected = payload.get("initial_conflict_detected")
    if isinstance(detected, bool):
        cleaned["initial_conflict_detected"] = detected
    if not cleaned["plan_version"] or not cleaned["rule"]:
        return cleaned, "fields_not_extractable"
    if "agent_a" not in cleaned["assignments"] or "agent_b" not in cleaned["assignments"]:
        return cleaned, "fields_not_extractable"
    if version and cleaned["plan_version"] != version:
        return cleaned, "fields_not_extractable"
    return cleaned, "ok"


def commit_contract(payload: dict[str, Any] | None, *, agent_id: str) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if any(key not in payload for key in ("agent_id", "plan_version", "confirm", "slot")):
        return dict(payload), "fields_not_extractable"
    if payload.get("agent_id") != agent_id:
        return dict(payload), "fields_not_extractable"
    if not isinstance(payload.get("confirm"), bool):
        return dict(payload), "fields_not_extractable"
    return {
        "agent_id": agent_id,
        "plan_version": str(payload.get("plan_version") or ""),
        "confirm": bool(payload.get("confirm")),
        "slot": None if payload.get("slot") in {None, ""} else str(payload.get("slot")),
    }, "ok"
