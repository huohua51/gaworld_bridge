"""Prompts and rule agent for exclusive keep/revise. No NONE, no need_change."""

from __future__ import annotations

import json
import re
from typing import Any

from exp_gm_oa_01.prompts import rule_decision as oa01_rule_decision
from exp_gm_oa_02.contract import ACTIONS, KEEP, REVISE


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


def rule_agent(task: dict[str, Any], notice: dict[str, Any] | None) -> dict[str, Any]:
    if not notice:
        return {}
    decided = oa01_rule_decision(task, notice)
    event_id = str(decided.get("evidence_event_id") or notice.get("event_id") or "")
    if decided.get("action") == "keep":
        return {"action": KEEP, "evidence_event_id": event_id}
    return {
        "action": REVISE,
        "target": decided.get("target"),
        "value": decided.get("value"),
        "evidence_event_id": event_id,
    }


def agent_prompt(task: dict[str, Any], *, notice: dict[str, Any], plan: dict[str, Any]) -> str:
    state = dict((notice or {}).get("current_state") or {})
    payload = {
        "current_plan": plan,
        "current_state": state,
        "event_id": notice.get("event_id"),
        "registered_target": task["target"],
        "action_enum": list(ACTIONS),
        "keep_schema": {"action": KEEP, "evidence_event_id": notice.get("event_id")},
        "revise_schema": {
            "action": REVISE,
            "target": task["target"],
            "value": "<registered modification>",
            "evidence_event_id": notice.get("event_id"),
        },
    }
    return (
        "你是计划维护者。看到当前登记状态后，提交一次最终行动。\n"
        "只输出一个 JSON 对象。动作必须是下面两个之一，不能混用字段。\n"
        f'保持不变：{{"action": "{KEEP}", "evidence_event_id": "<当前 event_id>"}}。\n'
        "保持不变时不要输出 target 或 value。既然不修改，就没有修改对象。\n"
        f'真正修改：{{"action": "{REVISE}", "target": "<registered_target>", '
        '"value": "<具体修改>", "evidence_event_id": "<当前 event_id>"}}。\n'
        "修改时必须同时给出 target 与 value。\n"
        "evidence_event_id 必须抄写当前事件的 event_id。\n"
        "不要输出 need_change，不要使用 NONE 占位符。\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n"
    )
