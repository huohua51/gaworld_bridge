"""Two equal-budget, single-call action protocols."""

from __future__ import annotations

import json
import re
from typing import Any

from exp_gm_oa_01.channel import NONE

LEGACY_FIELDS = ("action", "target", "value", "evidence_event_id")
GATE_FIELDS = ("need_change", "action", "target", "value", "evidence_event_id")
ACTIONS = ("keep", "revise")


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


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
        return None
    if value in (0, 1) and not isinstance(value, bool):
        return bool(value)
    return None


def action_contract(protocol: str, payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    fields = GATE_FIELDS if protocol == "need_change_gate" else LEGACY_FIELDS
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    missing = [key for key in fields if key not in payload]
    if missing:
        return dict(payload), "fields_not_extractable"
    action = {key: payload[key] for key in fields}
    if action.get("action") not in ACTIONS:
        return action, "ok"
    if protocol == "need_change_gate":
        flag = _as_bool(action.get("need_change"))
        if flag is None:
            return action, "fields_not_extractable"
        action["need_change"] = flag
    return action, "ok"


def rule_decision(task: dict[str, Any], notice: dict[str, Any]) -> dict[str, Any]:
    state = dict((notice or {}).get("current_state") or {})
    event_id = str(notice.get("event_id") or "")
    keep = {
        "need_change": False,
        "action": "keep",
        "target": NONE,
        "value": NONE,
        "evidence_event_id": event_id,
    }
    task_id = task["id"]
    if task_id == "appointment_update":
        appointment_time = str(state.get("appointment_time") or "")
        busy = {str(item) for item in (state.get("busy_times") or [])}
        if appointment_time == str(state.get("plan_time") or "") and appointment_time not in busy:
            return keep
        return {
            "need_change": True,
            "action": "revise",
            "target": "appointment_slot",
            "value": state.get("alternate_time"),
            "evidence_event_id": event_id,
        }
    if task_id == "resource_threshold":
        stock = int(state.get("stock"))
        min_need = int(state.get("min_need"))
        if stock >= min_need:
            return keep
        return {
            "need_change": True,
            "action": "revise",
            "target": "purchase_qty",
            "value": min_need - stock,
            "evidence_event_id": event_id,
        }
    if task_id == "responsibility_update":
        if bool(state.get("assignee_available")):
            return keep
        return {
            "need_change": True,
            "action": "revise",
            "target": "assignee_id",
            "value": state.get("backup_assignee"),
            "evidence_event_id": event_id,
        }
    raise KeyError(task_id)


def rule_agent(task: dict[str, Any], protocol: str, notice: dict[str, Any] | None) -> dict[str, Any]:
    if not notice:
        return {}
    decided = rule_decision(task, notice)
    if protocol == "legacy_direct":
        return {
            "action": decided["action"],
            "target": decided["target"],
            "value": decided["value"],
            "evidence_event_id": decided["evidence_event_id"],
        }
    return decided


def agent_prompt(
    task: dict[str, Any],
    *,
    protocol: str,
    notice: dict[str, Any],
    plan: dict[str, Any],
) -> str:
    state = dict((notice or {}).get("current_state") or {})
    payload = {
        "current_plan": plan,
        "current_state": state,
        "event_id": notice.get("event_id"),
        "registered_target": task["target"],
        "none_token": NONE,
        "action_enum": list(ACTIONS),
    }
    if protocol == "legacy_direct":
        contract = (
            "你是计划维护者。看到当前登记状态后，直接提交一次最终行动。\n"
            "只输出一个 JSON 对象，字段必须恰好是 action, target, value, evidence_event_id。\n"
            'action 必须是 "keep" 或 "revise"。\n'
            f'如果不需要改变计划：action="keep"，target 与 value 必须为 {NONE!r}。\n'
            "如果需要改变计划：action=\"revise\"，target 必须是 registered_target，value 填具体修改。\n"
            "evidence_event_id 必须抄写当前事件的 event_id。\n"
            "保持不变本身是合法行动。不要因为收到信息就默认必须修改。\n"
        )
    else:
        contract = (
            "你是计划维护者。看到当前登记状态后，先判断这条信息是否真的要求你改变行动，再提交一次最终行动。\n"
            "只输出一个 JSON 对象，字段必须恰好是 "
            "need_change, action, target, value, evidence_event_id。\n"
            "need_change 必须是 true 或 false。\n"
            'action 必须是 "keep" 或 "revise"。\n'
            f'need_change=false 时：必须 action="keep"，target 与 value 必须为 {NONE!r}。\n'
            'need_change=true 时：必须 action="revise"，并提交 registered_target 与具体 value。\n'
            "判断和行动不能互相矛盾。\n"
            "evidence_event_id 必须抄写当前事件的 event_id。\n"
            "看到信息以后，第一件事是判断它是否要求改变；保持不变本身也是合法行动。\n"
        )
    return contract + json.dumps(payload, ensure_ascii=False) + "\n"
