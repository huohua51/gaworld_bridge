"""Contracts. B boolean is self-assessment only. C forbids conflict fields."""

from __future__ import annotations

import json
import re
from typing import Any

A_KEY = "initial_conflict_detected"
B_KEY = "final_plan_conflict_free"


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


def contract_a(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or payload == {}:
        return {}, "empty"
    if A_KEY not in payload:
        return dict(payload), "fields_not_extractable"
    if not isinstance(payload.get(A_KEY), bool):
        return dict(payload), "fields_not_extractable"
    return {A_KEY: payload[A_KEY]}, "ok"


def contract_b(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or payload == {}:
        return {}, "empty"
    if B_KEY not in payload:
        return dict(payload), "fields_not_extractable"
    if not isinstance(payload.get(B_KEY), bool):
        return dict(payload), "fields_not_extractable"
    return {B_KEY: payload[B_KEY]}, "ok"


def contract_c(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or payload == {}:
        return {}, "empty"
    if any(key in payload for key in (A_KEY, B_KEY, "conflict")):
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


def action_contract(component: str, payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if component == "A":
        return contract_a(payload)
    if component == "B":
        return contract_b(payload)
    return contract_c(payload)
