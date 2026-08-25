"""Rule roles and LLM prompts for TASK-I1."""

from __future__ import annotations

import json
import re
from typing import Any

from holdout_i1.probes import variant_spec


def parse_json_object(text: str) -> dict[str, Any] | list[Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw)
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        payload = json.loads(raw)
        if isinstance(payload, (dict, list)):
            return payload
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]|\{.*\}", raw, re.S)
    if match:
        payload = json.loads(match.group(0))
        if isinstance(payload, (dict, list)):
            return payload
    raise ValueError("output is not JSON")


def rule_observer(probe: dict, variant: str) -> list[dict[str, Any]]:
    return list(variant_spec(probe, variant)["signals"])


def rule_verifier(raw_messages: list[dict[str, Any]], private: dict[str, Any], version: str) -> dict[str, Any]:
    trusted = private.get("trusted_source_id")
    match = next((item for item in raw_messages if item.get("source_id") == trusted), None)
    if match is None:
        return {}
    return {
        "verified_state": match["reported_state"],
        "source_id": match["source_id"],
        "state_version": version,
    }


def rule_dispatcher(probe: dict, *, verified: dict[str, Any] | None, raw: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not verified:
        return {}
    state = verified.get("verified_state")
    value = probe["value_a"] if state == probe["state_a"] else probe["value_b"] if state == probe["state_b"] else ""
    if not value:
        return {}
    return {
        "action": probe["action"],
        "value": value,
        "adopted_state_version": verified.get("state_version", ""),
        "evidence_message_id": verified.get("message_id", ""),
    }


def observer_prompt(probe: dict, signals: list[dict[str, Any]]) -> str:
    return (
        "你是观察员。把下面两个来源的报告原样发出，不要判断谁可信，不要做决策。\n"
        "只输出 JSON 数组，每项含 source_id 与 reported_state。\n"
        f"【场景】{probe['id']}\n"
        f"【报告】{json.dumps(signals, ensure_ascii=False)}\n"
    )


def verifier_prompt(raw_messages: list[dict[str, Any]], private: dict[str, Any], version: str) -> str:
    return (
        "你是核验员。根据私有可信表，从原始观测里选出可信来源报告的状态。\n"
        "不能提交最终动作。只输出一个 JSON 对象，字段为 verified_state, source_id, state_version。\n"
        f"【可信表】{json.dumps(private, ensure_ascii=False)}\n"
        f"【原始观测】{json.dumps(raw_messages, ensure_ascii=False)}\n"
        f"【本轮版本】{version}\n"
    )


def action_contract(probe: dict, payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    action = str(payload.get("action") or "")
    value = str(payload.get("value") or "")
    legal = {probe["value_a"], probe["value_b"]}
    if action in legal and value == probe["action"]:
        return dict(payload), "swapped_action_value"
    if action != probe["action"]:
        return dict(payload), "action_not_in_contract"
    if value not in legal:
        return dict(payload), "value_not_in_contract"
    return dict(payload), "ok"


def dispatcher_prompt(probe: dict, *, verified: dict[str, Any] | None, raw: list[dict[str, Any]] | None, extra: str = "") -> str:
    action_name = probe["action"]
    legal = [probe["value_a"], probe["value_b"]]
    payload = {
        "action": action_name,
        "value_enum": legal,
        "rule": probe["rule"],
        "wrong_example": {"action": legal[0], "value": action_name},
        "right_example_shape": {
            "action": action_name,
            "value": "<one of value_enum>",
            "adopted_state_version": "<from verified_message>",
            "evidence_message_id": "<from verified_message>",
        },
    }
    if verified:
        payload["verified_message"] = verified
    if raw:
        payload["raw_signals"] = raw
        payload["note"] = "这是未经核验的冲突信号。没有核验消息。"
    if extra:
        payload["note"] = extra
    return (
        "你是调度员。只能根据已送达的核验消息做最终动作。不能读取可信来源表。\n"
        "只输出一个 JSON 对象，字段为 action, value, adopted_state_version, evidence_message_id。\n"
        f"action 必须恰好是 {action_name!r}，禁止填 {legal[0]!r} 或 {legal[1]!r}。\n"
        f"value 必须是 {legal[0]!r} 或 {legal[1]!r}，禁止填 {action_name!r}。\n"
        "禁止把 action 与 value 对调。wrong_example 是错误示范，不要照抄。\n"
        "若没有核验消息，不要编造 evidence_message_id。\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
    )
