"""Flat visit-action contract. No nested review JSON."""

from __future__ import annotations

import json
import re
from typing import Any

from exp_gm_01.probes import destination_enum, variant_spec
from gaworld.life.venue import ACTION_FIELDS, ACTION_NAME


def parse_json_object(text: str) -> dict[str, Any]:
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
    if match:
        payload = json.loads(match.group(0))
        if isinstance(payload, dict):
            return payload
    raise ValueError("output is not a JSON object")


def flatten_action(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        return {}
    if isinstance(payload.get("target_action"), dict):
        payload = payload["target_action"]
    return dict(payload)


def action_contract(probe: dict, payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    flat = flatten_action(payload)
    if not flat:
        return {}, "empty"
    missing = [key for key in ACTION_FIELDS if key not in flat]
    if missing:
        return dict(flat), "fields_not_extractable"
    action = dict(flat)
    legal = set(destination_enum(probe))
    if action.get("action") != ACTION_NAME:
        return action, "action_not_in_contract"
    if action.get("destination") not in legal:
        return action, "destination_not_in_contract"
    if action.get("slot_id") != probe["slot_id"]:
        return action, "slot_not_in_contract"
    return action, "ok"


def rule_agent(probe: dict, *, notice: dict[str, Any] | None) -> dict[str, Any]:
    spec = variant_spec(probe, "control")
    if notice:
        status = str(notice.get("status") or "")
        dest = probe["original"] if status == "open" else probe["alternative"] if status == "closed" else ""
        if not dest:
            return {}
        return {
            "action": ACTION_NAME,
            "destination": dest,
            "slot_id": probe["slot_id"],
            "adopted_state_version": str(notice.get("state_version") or spec["state_version"]),
            "evidence_event_id": str(notice.get("event_id") or ""),
        }
    return {
        "action": ACTION_NAME,
        "destination": probe["original"],
        "slot_id": probe["slot_id"],
        "adopted_state_version": "",
        "evidence_event_id": "",
    }


def agent_prompt(
    probe: dict,
    *,
    notice: dict[str, Any] | None,
    schedule: list[dict[str, Any]],
    extra: str = "",
) -> str:
    payload = {
        "action": ACTION_NAME,
        "destination_enum": destination_enum(probe),
        "slot_id": probe["slot_id"],
        "required_type": probe["required_type"],
        "origin": probe["origin"],
        "planned_destination": probe["original"],
        "activity": probe["activity"],
        "rule": probe["rule"],
        "current_schedule": schedule,
        "fields": list(ACTION_FIELDS),
        "right_example_shape": {
            "action": ACTION_NAME,
            "destination": "<one of destination_enum>",
            "slot_id": probe["slot_id"],
            "adopted_state_version": "<from venue notice, or empty string>",
            "evidence_event_id": "<from venue notice, or empty string>",
        },
    }
    if notice:
        payload["venue_notice"] = {
            "event_id": notice.get("event_id"),
            "venue_id": notice.get("venue_id"),
            "status": notice.get("status"),
            "state_version": notice.get("state_version"),
            "slot_id": notice.get("slot_id"),
        }
        if notice.get("direct") and notice.get("venues"):
            payload["current_venue_state"] = notice.get("venues")
    else:
        payload["venue_notice"] = None
        payload["note"] = "没有收到场所状态事件。不要编造 evidence_event_id。"
    if extra:
        payload["note"] = extra
    return (
        "你是出行中的个人。出发前根据已送达的场所状态，提交一次改道动作。\n"
        "只输出一个 JSON 对象，字段必须恰好是 action, destination, slot_id, adopted_state_version, evidence_event_id。\n"
        f"action 必须恰好是 {ACTION_NAME!r}。\n"
        f"destination 必须是 {destination_enum(probe)!r} 之一。\n"
        f"slot_id 必须恰好是 {probe['slot_id']!r}。\n"
        "若没有场所状态事件，adopted_state_version 与 evidence_event_id 填空字符串，不要编造。\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
    )
