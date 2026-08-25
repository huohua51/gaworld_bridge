"""Assignments only. No conflict booleans. No oracle slots as hints."""

from __future__ import annotations

import json
import re
from typing import Any


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


def action_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or payload == {}:
        return {}, "empty"
    if any(key in payload for key in ("conflict", "initial_conflict_detected", "final_plan_conflict_free")):
        return dict(payload), "conflict_field_not_allowed"
    assignments = payload.get("assignments")
    if not isinstance(assignments, dict):
        return dict(payload), "fields_not_extractable"
    if "agent_a" not in assignments or "agent_b" not in assignments:
        return dict(payload), "fields_not_extractable"
    a = assignments.get("agent_a")
    b = assignments.get("agent_b")
    if not isinstance(a, str) or not a.strip() or not isinstance(b, str) or not b.strip():
        return dict(payload), "fields_not_extractable"
    return {"assignments": {"agent_a": a, "agent_b": b}}, "ok"
