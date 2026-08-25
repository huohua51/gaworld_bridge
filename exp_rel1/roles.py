"""Rule roles and LLM prompts for TASK-REL1."""

from __future__ import annotations

import json
import re
from typing import Any

from exp_rel1.probes import current_signals


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


def _person_correct_counts(history: list[dict[str, Any]]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for row in history:
        outcome = str(row.get("outcome") or "")
        reports = dict(row.get("reports") or {})
        for person_id, state in reports.items():
            scores.setdefault(str(person_id), 0)
            if str(state) == outcome:
                scores[str(person_id)] += 1
    return scores


def _state_of(currents: list[dict[str, Any]], person_id: str) -> str:
    match = next((item for item in currents if item.get("person_id") == person_id), None)
    return str((match or {}).get("reported_state") or "")


def rule_observer(probe: dict, variant: str) -> list[dict[str, Any]]:
    return list(current_signals(probe))


def rule_trust_updater(
    history: list[dict[str, Any]],
    currents: list[dict[str, Any]],
    version: str,
    phase: str,
) -> dict[str, Any]:
    if not history:
        return {}
    if phase == "update":
        last = history[-1]
        reports = dict(last.get("reports") or {})
        outcome = str(last.get("outcome") or "")
        trusted = next((pid for pid, state in reports.items() if str(state) == outcome), "")
    else:
        scores = _person_correct_counts(history)
        if not scores:
            return {}
        trusted = max(scores, key=lambda pid: (scores[pid], pid))
    if not trusted:
        return {}
    other = next((item.get("person_id") for item in currents if item.get("person_id") != trusted), "")
    state = _state_of(currents, trusted)
    if not state:
        return {}
    return {
        "trusted_person_id": trusted,
        "trusted_state": state,
        "trust_version": version,
        "other_person_id": other,
        "evidence_count": len(history) if phase != "update" else 1,
    }


def rule_dispatcher(probe: dict, *, trust: dict[str, Any] | None, round_name: str) -> dict[str, Any]:
    if not trust:
        return {}
    state = trust.get("trusted_state")
    value = probe["value_a"] if state == probe["state_a"] else probe["value_b"] if state == probe["state_b"] else ""
    if not value:
        return {}
    return {
        "action": probe["action"],
        "value": value,
        "adopted_trust_version": trust.get("trust_version", ""),
        "evidence_message_id": trust.get("message_id", ""),
        "round": round_name,
    }


def observer_prompt(probe: dict, signals: list[dict[str, Any]]) -> str:
    return (
        "你是观察员。把下面两个人的当前报告原样发出，不要判断谁可信，不要做决策。\n"
        "只输出 JSON 数组，每项含 person_id 与 reported_state。\n"
        f"【场景】{probe['id']}\n"
        f"【报告】{json.dumps(signals, ensure_ascii=False)}\n"
    )


def trust_updater_prompt(
    history: list[dict[str, Any]],
    currents: list[dict[str, Any]],
    version: str,
    phase: str,
) -> str:
    if phase == "update":
        rule = (
            "现在是更新阶段。登记规则 latest_is_binding=true："
            "必须根据历史里最新一条带 outcome 的记录更新来源可靠性，"
            "刚被证明正确的人覆盖历史累计多数。"
        )
    else:
        rule = "现在是形成阶段。根据历史里谁更常被证明正确，形成初始信任。"
    return (
        "你是信任更新员。只能根据私有历史账本和当前报告，输出信任状态。不能提交最终动作。\n"
        f"{rule}\n"
        "只输出一个 JSON 对象，字段为 trusted_person_id, trusted_state, trust_version, other_person_id, evidence_count。\n"
        f"【历史账本】{json.dumps(history, ensure_ascii=False)}\n"
        f"【当前报告】{json.dumps(currents, ensure_ascii=False)}\n"
        f"【本轮版本】{version}\n"
    )


def dispatcher_prompt(
    probe: dict,
    *,
    trust: dict[str, Any] | None,
    currents: list[dict[str, Any]] | None,
    round_name: str,
    extra: str = "",
) -> str:
    payload = {
        "action_name": probe["action"],
        "rule": probe["rule"],
        "legal_values": [probe["value_a"], probe["value_b"]],
        "round": round_name,
    }
    if trust:
        payload["trust_message"] = trust
    if currents:
        payload["current_reports"] = currents
        payload["note"] = "这是未经信任更新的冲突报告。没有信任状态。"
    if extra:
        payload["note"] = extra
    return (
        "你是调度员。只能根据已送达的信任状态做最终动作。不能读取历史账本。\n"
        "只输出一个 JSON 对象，字段为 action, value, adopted_trust_version, evidence_message_id, round。\n"
        "round 必须是 formation 或 update，与本轮一致。\n"
        "若没有信任消息，不要编造 evidence_message_id。\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
    )
