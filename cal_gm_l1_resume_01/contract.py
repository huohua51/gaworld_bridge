"""Coordinator resume JSON: completed_steps, resume_step, remaining_steps."""

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


def _str_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    out = []
    for item in value:
        text = str(item).strip()
        if not text:
            return None
        out.append(text)
    return out


def resume_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if "completed_steps" not in payload or "resume_step" not in payload or "remaining_steps" not in payload:
        return dict(payload), "fields_not_extractable"
    completed = _str_list(payload.get("completed_steps"))
    remaining = _str_list(payload.get("remaining_steps"))
    resume = str(payload.get("resume_step") or "").strip()
    if completed is None or remaining is None or not resume:
        return dict(payload), "fields_not_extractable"
    return {"completed_steps": completed, "resume_step": resume, "remaining_steps": remaining}, "ok"
