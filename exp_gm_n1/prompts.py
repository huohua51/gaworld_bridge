"""Prompts and Rule agents. Hidden oracle files never enter prompts."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_n1.contract import KEEP, REVISE
from exp_gm_n1.loader import source_private


def rule_source(task: dict, variant: str) -> dict[str, Any]:
    private = source_private(task, variant)
    return {
        "source_id": private["source_id"],
        "reported_state": private["reported_state"],
        "state_version": private["state_version"],
    }


def rule_relay(task: dict, raw_messages: list[dict[str, Any]], trusted_source_id: str) -> dict[str, Any]:
    for item in raw_messages:
        if item.get("source_id") == trusted_source_id:
            state = item.get("reported_state")
            return {
                "verified_state": state,
                "source_id": item.get("source_id"),
                "state_version": "v2" if state == task["intervention_state"] else "v1",
            }
    return {}


def rule_decision(task: dict, *, inbox: list[dict[str, Any]]) -> dict[str, Any]:
    message = inbox[0] if inbox else None
    evidence = str((message or {}).get("message_id") or "none")
    state = str((message or {}).get("verified_state") or "")
    if state == task["intervention_state"]:
        return {
            "action": REVISE,
            "target": task["target"],
            "value": task["intervention_value"],
            "evidence_message_id": evidence,
        }
    return {"action": KEEP, "evidence_message_id": evidence}


def source_prompt(private: dict[str, Any]) -> str:
    return (
        "你是 Source。你掌握的状态是私有的，只根据私有状态发出报告。\n"
        "只输出一个 JSON 对象：\n"
        '{"source_id": "<source_id>", "reported_state": "<状态>", "state_version": "v1 或 v2"}\n'
        "不要编造隐藏测试，不要输出 DecisionMaker 动作。\n"
        f"【私有状态】{json.dumps(private, ensure_ascii=False)}\n"
    )


def relay_prompt(raw_messages: list[dict[str, Any]], trusted: dict[str, Any]) -> str:
    return (
        "你是 Relay。根据原始报告和可信来源核验状态。不要改 DecisionMaker 的计划。\n"
        "只输出一个 JSON 对象：\n"
        '{"verified_state": "<状态>", "source_id": "<source_id>", "state_version": "v1 或 v2"}\n'
        "只核验 trusted_source_id 对应的来源。\n"
        f"【可信来源】{json.dumps(trusted, ensure_ascii=False)}\n"
        f"【原始报告】{json.dumps(raw_messages, ensure_ascii=False)}\n"
    )


def decision_prompt(task: dict[str, Any], *, plan: dict[str, Any], inbox: list[dict[str, Any]]) -> str:
    return (
        "你是 DecisionMaker。只能根据当前计划和收件箱里已送达的核实消息做决定。\n"
        "收件箱为空时保持当前计划。不要读取全局状态，不要编造消息。\n"
        "只输出一个 JSON 对象。动作必须是下面两个之一，不能混用字段。\n"
        f'保持：{{"action": "{KEEP}", "evidence_message_id": "<message_id 或 none>"}}。保持时不要输出 target 或 value。\n'
        f'修改：{{"action": "{REVISE}", "target": "{task["target"]}", "value": "<新值>", '
        '"evidence_message_id": "<message_id>"}}。\n'
        "不要输出 need_change，不要使用 NONE。\n"
        f"【当前计划】{json.dumps(plan, ensure_ascii=False)}\n"
        f"【收件箱】{json.dumps(inbox, ensure_ascii=False)}\n"
        f"【任务说明】{task['brief']}\n"
    )
