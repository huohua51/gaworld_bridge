"""Flat care-action contract. Control must fill NONE placeholders."""

from __future__ import annotations

import json
import re
from typing import Any

from exp_gm_02.probes import caregiver_enum, patient_enum, variant_spec
from gaworld.life.family import ACTION_FIELDS, ACTIONS, NONE, SCHEDULE_DECISIONS


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
    try:
        action["expense_amount"] = int(action["expense_amount"])
    except (TypeError, ValueError):
        return action, "fields_not_extractable"
    if action.get("action") not in ACTIONS:
        return action, "action_not_in_contract"
    if action.get("schedule_decision") not in SCHEDULE_DECISIONS:
        return action, "slot_not_in_contract"
    if action.get("caregiver_id") not in set(caregiver_enum(probe)):
        return action, "wrong_caregiver_selected"
    if action.get("patient_id") not in set(patient_enum(probe)):
        return action, "action_not_in_contract"
    if action.get("slot_id") != probe["conflict_slot_id"]:
        return action, "slot_not_in_contract"
    return action, "ok"


def control_placeholder(probe: dict) -> dict[str, Any]:
    return {
        "action": "keep_schedule",
        "caregiver_id": NONE,
        "patient_id": NONE,
        "event_id": NONE,
        "slot_id": probe["conflict_slot_id"],
        "schedule_decision": "keep",
        "expense_amount": 0,
        "adopted_state_version": "v1",
        "evidence_event_id": NONE,
    }


def intervention_action(probe: dict, notice: dict[str, Any]) -> dict[str, Any]:
    event_id = str(notice.get("event_id") or NONE)
    return {
        "action": "provide_care",
        "caregiver_id": probe["legal_caregiver_id"],
        "patient_id": probe["patient_id"],
        "event_id": event_id,
        "slot_id": probe["conflict_slot_id"],
        "schedule_decision": "cancel",
        "expense_amount": int(probe["registered_expense"]),
        "adopted_state_version": str(notice.get("state_version") or "v2"),
        "evidence_event_id": event_id,
    }


def rule_agent(probe: dict, *, notice: dict[str, Any] | None) -> dict[str, Any]:
    if notice and bool(notice.get("requires_care")):
        return intervention_action(probe, notice)
    return control_placeholder(probe)


def agent_prompt(
    probe: dict,
    *,
    notice: dict[str, Any] | None,
    schedule: list[dict[str, Any]],
    extra: str = "",
) -> str:
    spec = variant_spec(probe, "control")
    payload = {
        "action_enum": list(ACTIONS),
        "schedule_decision_enum": list(SCHEDULE_DECISIONS),
        "caregiver_enum": caregiver_enum(probe),
        "patient_enum": patient_enum(probe),
        "slot_id": probe["conflict_slot_id"],
        "registered_expense": probe["registered_expense"],
        "legal_caregiver_id": probe["legal_caregiver_id"],
        "patient_id": probe["patient_id"],
        "requires_care_flag_name": "requires_care",
        "rule": probe["rule"],
        "current_schedule": schedule,
        "fields": list(ACTION_FIELDS),
        "control_placeholder": control_placeholder(probe),
        "none_token": NONE,
    }
    if notice:
        payload["family_notice"] = {
            "event_id": notice.get("event_id"),
            "requires_care": notice.get("requires_care"),
            "patient_id": notice.get("patient_id"),
            "legal_caregiver_id": notice.get("legal_caregiver_id"),
            "slot_id": notice.get("slot_id"),
            "expense_amount": notice.get("expense_amount"),
            "state_version": notice.get("state_version"),
        }
    else:
        payload["family_notice"] = None
        payload["note"] = "没有收到家庭照料事件。必须输出完整占位字段，不要缺字段。"
    if extra:
        payload["note"] = extra
    return (
        "你是家庭日程决策者。只能根据已送达的登记照料事件提交一次扁平动作。\n"
        "只输出一个 JSON 对象，字段必须恰好是 "
        "action, caregiver_id, patient_id, event_id, slot_id, schedule_decision, "
        "expense_amount, adopted_state_version, evidence_event_id。\n"
        f"action 必须是 {list(ACTIONS)!r} 之一。\n"
        f"schedule_decision 必须是 {list(SCHEDULE_DECISIONS)!r} 之一。\n"
        f"没有照料事件或 requires_care=false 时，必须使用 control_placeholder，"
        f"caregiver_id/patient_id/event_id/evidence_event_id 填 {NONE!r}，expense_amount 填 0。\n"
        "不要因为“看起来应该更有适应性”而在没有事件时主动认领照料。\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
    )
