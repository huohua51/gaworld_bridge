"""Step, checkpoint, handoff and resume contracts. Platform stamps ckpt-001."""

from __future__ import annotations

import json
import re
from typing import Any

CHECKPOINT_VERSION = "ckpt-001"
EXTRACTABLE_STEP_ERRORS = {"ok", "idle"}


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


def step_contract(payload: dict[str, Any] | None, *, worker_id: str) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if payload.get("action") == "idle":
        if payload.get("agent_id") != worker_id and payload.get("worker_id") != worker_id:
            return dict(payload), "fields_not_extractable"
        return {"worker_id": worker_id, "action": "idle"}, "idle"
    worker = str(payload.get("worker_id") or payload.get("agent_id") or "")
    if worker != worker_id:
        return dict(payload), "fields_not_extractable"
    if not _present(payload, "step_id") or "output" not in payload:
        return dict(payload), "fields_not_extractable"
    output = payload.get("output")
    if not isinstance(output, dict):
        return dict(payload), "fields_not_extractable"
    return {"worker_id": worker_id, "step_id": str(payload["step_id"]), "output": dict(output)}, "ok"


def checkpoint_contract(payload: dict[str, Any] | None, *, worker_id: str) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    worker = str(payload.get("worker_id") or payload.get("agent_id") or "")
    if worker != worker_id:
        return dict(payload), "fields_not_extractable"
    completed = payload.get("completed_steps")
    outputs = payload.get("outputs")
    if not isinstance(completed, list) or not completed or not isinstance(outputs, dict):
        return dict(payload), "fields_not_extractable"
    return {
        "worker_id": worker_id,
        "completed_steps": [str(item) for item in completed],
        "outputs": dict(outputs),
    }, "ok"


def handoff_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    needed = ("successor", "checkpoint_version", "resume_step", "completed_steps", "remaining_steps")
    if any(not _present(payload, key) for key in needed):
        return dict(payload), "fields_not_extractable"
    successor = str(payload["successor"])
    if successor not in {"worker_a", "worker_b"}:
        return dict(payload), "fields_not_extractable"
    completed = payload.get("completed_steps")
    remaining = payload.get("remaining_steps")
    if not isinstance(completed, list) or not completed or not isinstance(remaining, list) or not remaining:
        return dict(payload), "fields_not_extractable"
    resume = str(payload["resume_step"]).strip()
    if not resume:
        return dict(payload), "fields_not_extractable"
    return {
        "successor": successor,
        "checkpoint_version": str(payload["checkpoint_version"]),
        "resume_step": resume,
        "completed_steps": [str(item) for item in completed],
        "remaining_steps": [str(item) for item in remaining],
    }, "ok"


def resume_contract(payload: dict[str, Any] | None, *, worker_id: str) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if payload.get("action") == "idle":
        return {"worker_id": worker_id, "action": "idle"}, "idle"
    worker = str(payload.get("worker_id") or payload.get("agent_id") or "")
    if worker != worker_id:
        return dict(payload), "fields_not_extractable"
    if any(not _present(payload, key) for key in ("checkpoint_version", "resume_step")):
        return dict(payload), "fields_not_extractable"
    return {
        "worker_id": worker_id,
        "checkpoint_version": str(payload["checkpoint_version"]),
        "resume_step": str(payload["resume_step"]),
    }, "ok"


def direct_contract(payload: dict[str, Any] | None, *, required_ids: list[str]) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    steps = payload.get("steps")
    if not isinstance(steps, dict):
        return dict(payload), "fields_not_extractable"
    cleaned: dict[str, Any] = {}
    for key, value in steps.items():
        if not isinstance(value, dict):
            continue
        if set(value) == {"output"} and isinstance(value.get("output"), dict):
            cleaned[str(key)] = dict(value["output"])
        else:
            cleaned[str(key)] = dict(value)
    if any(step_id not in cleaned for step_id in required_ids):
        return {"steps": cleaned}, "fields_not_extractable"
    return {"steps": cleaned}, "ok"
