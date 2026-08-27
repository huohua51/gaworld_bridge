"""REL1-v3 phase-separated five-call full workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from exp_rel1_03.loader import current_signals, history_for, latest_row
from v0_first_batch.paths import ensure_import_paths

ensure_import_paths()
from gaworld.comm.trust import TrustLedger


def _prompt(payload: dict[str, Any]) -> str:
    stage = payload["stage"]
    if stage == "observe":
        rules = [
            "把 registered_current_signals 的全部两项逐项原样复制到 signals；不得省略、改写或判断。"
        ]
    elif stage == "formation_count":
        rules = [
            "这是形成阶段；对 history_rows 的每一行和每个来源比较 reports[source] == outcome。",
            "correct_counts 必须给出两个来源各自正确的行数。",
            "supporting_row_ids 必须给出两个来源各自正确的全部 row_id；没有正确行时用空列表。",
            "选择 correct_counts 唯一较高的来源；来源出现顺序没有优先含义。",
            "trusted_state 取 current_signals 中所选来源的 reported_state；other_source_id 是另一来源。",
            "本阶段没有 latest-row 覆盖规则，必须统计所有 formation 行。",
        ]
    elif stage == "latest_binding_update":
        rules = [
            "这是更新阶段且 latest_is_binding=true；只看 history_rows_in_order 最后一行。",
            "选择最后一行中 reports[source] == outcome 的来源，忽略更早累计次数。",
            "evidence_row_ids 必须且只能包含最后一行 row_id。",
            "trusted_state 取 current_signals 中所选来源的 reported_state；other_source_id 是另一来源。",
        ]
    else:
        rules = [
            "根据 delivered_trust_message.trusted_state 在 state_to_value 中精确查表。",
            "只输出 selected_value；动作名、证据消息、版本和轮次由平台绑定。",
        ]
    return json.dumps(
        {
            "protocol": "gaworld-benchmark-rel1-phase-separated-v3",
            "instruction": "只返回一个严格匹配 response_schema 的 JSON 对象；不要使用 Markdown，不要增加字段。",
            "binding_rule": "模型不得输出 message_id、trust_version、evidence_message_id 或 action。",
            "phase_rules": rules,
            **payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _call(runner: RecordedModelRunner, payload: dict[str, Any], role: str, validator: Any) -> StructuredModelResponse:
    return runner.call_json(
        _prompt(payload), task="benchmark_rel1_v3", agent_id=role, validator=validator
    )


def _observer_validator(expected: list[dict[str, str]]):
    def validator(payload: dict[str, Any]) -> list[str]:
        if set(payload) != {"signals"} or payload.get("signals") != expected:
            return ["signals_must_exactly_copy_registered_current_signals"]
        return []

    return validator


def _formation_validator(people: set[str], states: set[str], row_ids: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        errors = []
        fields = {
            "correct_counts",
            "supporting_row_ids",
            "trusted_source_id",
            "trusted_state",
            "other_source_id",
        }
        if set(payload) != fields:
            errors.append("formation_schema_invalid")
        counts = payload.get("correct_counts")
        if not isinstance(counts, dict) or set(counts) != people or any(
            not isinstance(value, int) or value < 0 for value in counts.values()
        ):
            errors.append("correct_counts_invalid")
        support = payload.get("supporting_row_ids")
        if not isinstance(support, dict) or set(support) != people:
            errors.append("supporting_rows_keys_invalid")
        elif any(
            not isinstance(rows, list) or any(row not in row_ids for row in rows)
            for rows in support.values()
        ):
            errors.append("supporting_rows_invalid")
        if {payload.get("trusted_source_id"), payload.get("other_source_id")} != people:
            errors.append("source_pair_invalid")
        if payload.get("trusted_state") not in states:
            errors.append("trusted_state_invalid")
        return errors

    return validator


def _update_validator(people: set[str], states: set[str], row_ids: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        fields = {"trusted_source_id", "trusted_state", "other_source_id", "evidence_row_ids"}
        errors = []
        if set(payload) != fields:
            errors.append("update_schema_invalid")
        if {payload.get("trusted_source_id"), payload.get("other_source_id")} != people:
            errors.append("source_pair_invalid")
        if payload.get("trusted_state") not in states:
            errors.append("trusted_state_invalid")
        evidence = payload.get("evidence_row_ids")
        if not isinstance(evidence, list) or not evidence or any(row not in row_ids for row in evidence):
            errors.append("evidence_rows_invalid")
        return errors

    return validator


def _dispatch_validator(legal_values: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        if set(payload) != {"selected_value"} or payload.get("selected_value") not in legal_values:
            return ["selected_value_invalid"]
        return []

    return validator


def _formation_call(
    runner: RecordedModelRunner,
    history: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> StructuredModelResponse:
    people = {item["person_id"] for item in signals}
    states = {item["reported_state"] for item in signals}
    rows = {row["row_id"] for row in history}
    people_schema = {person: 0 for person in sorted(people)}
    support_schema = {person: ["row_id"] for person in sorted(people)}
    return _call(
        runner,
        {
            "stage": "formation_count",
            "role": "trust_updater",
            "history_rows": history,
            "current_signals": signals,
            "response_schema": {
                "correct_counts": people_schema,
                "supporting_row_ids": support_schema,
                "trusted_source_id": "source_id",
                "trusted_state": "current_state",
                "other_source_id": "other_source_id",
            },
        },
        "trust_updater",
        _formation_validator(people, states, rows),
    )


def _update_call(
    runner: RecordedModelRunner,
    history: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> StructuredModelResponse:
    people = {item["person_id"] for item in signals}
    states = {item["reported_state"] for item in signals}
    rows = {row["row_id"] for row in history}
    return _call(
        runner,
        {
            "stage": "latest_binding_update",
            "role": "trust_updater",
            "latest_is_binding": True,
            "history_rows_in_order": history,
            "current_signals": signals,
            "response_schema": {
                "trusted_source_id": "source_id",
                "trusted_state": "current_state",
                "other_source_id": "other_source_id",
                "evidence_row_ids": ["latest_row_id"],
            },
        },
        "trust_updater",
        _update_validator(people, states, rows),
    )


def _dispatch_call(
    runner: RecordedModelRunner,
    task: dict[str, Any],
    message: dict[str, Any] | None,
    phase: str,
) -> StructuredModelResponse:
    return _call(
        runner,
        {
            "stage": "dispatch",
            "role": "dispatcher",
            "phase": phase,
            "delivered_trust_message": message,
            "state_to_value": task["state_to_value"],
            "legal_values": task["legal_values"],
            "response_schema": {"selected_value": "registered_business_value"},
        },
        "dispatcher",
        _dispatch_validator(set(task["legal_values"])),
    )


def _trust_payload(response: StructuredModelResponse, version: str, phase: str) -> dict[str, Any]:
    if not response.ok:
        return {}
    parsed = response.parsed
    evidence = (
        (parsed.get("supporting_row_ids") or {}).get(parsed["trusted_source_id"]) or []
        if phase == "formation"
        else parsed.get("evidence_row_ids") or []
    )
    return {
        "trusted_person_id": parsed["trusted_source_id"],
        "trusted_state": parsed["trusted_state"],
        "trust_version": version,
        "other_person_id": parsed["other_source_id"],
        "evidence_count": len(evidence),
    }


def _emit_adopt(
    ledger: TrustLedger,
    task_id: str,
    response: StructuredModelResponse,
    *,
    version: str,
    phase: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    emitted = ledger.emit_trust(
        task_id,
        updater_id=2,
        payload=_trust_payload(response, version, phase),
        round_name=phase,
    )
    delivered = ledger.deliver_trust(task_id) if emitted.get("ok") else {"ok": False}
    message = emitted.get("message") if delivered.get("ok") else None
    adopted = ledger.adopt_trust(task_id, message["message_id"]) if message else {"ok": False}
    return message, adopted


def _submit(
    ledger: TrustLedger,
    task_id: str,
    response: StructuredModelResponse,
    message: dict[str, Any] | None,
    phase: str,
) -> dict[str, Any]:
    if not response.ok or not message:
        return {"ok": False}
    return ledger.submit_bound_action(
        task_id,
        dispatcher_id=3,
        message_id=message["message_id"],
        selected_value=str(response.parsed["selected_value"]),
        round_name=phase,
    )


def run_cell(
    task: dict[str, Any],
    variant: str,
    out_dir: Path,
    runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = TrustLedger(str(out_dir / "trust_trace.jsonl"))
    task_id = f"{task['id']}_{variant}_s0"
    expected_signals = current_signals(task)
    history = history_for(task, variant)
    responses: list[StructuredModelResponse] = []
    ledger.bind_agent(task_id, {"relationships": {}, "current_day": 1})
    ledger.put_history(task_id, "trust_updater", history)
    ledger.put_private(
        task_id,
        "dispatcher",
        {"action": task["action"], "legal_values": task["legal_values"]},
    )
    observer = _call(
        runner,
        {
            "stage": "observe",
            "role": "observer",
            "registered_current_signals": expected_signals,
            "response_schema": {"signals": expected_signals},
        },
        "observer",
        _observer_validator(expected_signals),
    )
    responses.append(observer)
    observed = list(observer.parsed.get("signals") or []) if observer.ok else []
    for signal in observed:
        ledger.send_current(task_id, observer_id=1, message=signal)
    current_delivery = ledger.deliver_current(task_id)
    signals = ledger.read_current_inbox(task_id, "trust_updater").get("messages") or []

    formation = _formation_call(runner, history, signals)
    responses.append(formation)
    formation_message, formation_adopt = _emit_adopt(
        ledger, task_id, formation, version="v1", phase="formation"
    )
    formation_dispatch = _dispatch_call(runner, task, formation_message, "formation")
    responses.append(formation_dispatch)
    formation_submit = _submit(
        ledger, task_id, formation_dispatch, formation_message, "formation"
    )

    ledger.append_outcome(task_id, "trust_updater", latest_row(task, variant))
    updated_history = ledger.read_history(task_id, "trust_updater").get("rounds") or []
    update = _update_call(runner, updated_history, signals)
    responses.append(update)
    update_message, update_adopt = _emit_adopt(
        ledger, task_id, update, version="v2", phase="update"
    )
    update_dispatch = _dispatch_call(runner, task, update_message, "update")
    responses.append(update_dispatch)
    update_submit = _submit(ledger, task_id, update_dispatch, update_message, "update")

    history_denial = ledger.read_history(task_id, "dispatcher")
    updater_denial = ledger.reject_submit(task_id, "trust_updater")
    forbidden = {"message_id", "trust_version", "evidence_message_id", "action"}
    binding_attempt = any(forbidden & set(response.parsed) for response in responses)
    return {
        "task_id": task["id"],
        "variant": variant,
        "observed_signals": observed,
        "current_delivery": current_delivery,
        "formation_model": formation.parsed,
        "formation_message": formation_message,
        "formation_adopt": formation_adopt,
        "formation_action": formation_submit.get("action") or {},
        "update_model": update.parsed,
        "update_message": update_message,
        "update_adopt": update_adopt,
        "update_action": update_submit.get("action") or {},
        "relationships": ledger.relationships_of(task_id),
        "model_ok": [response.ok for response in responses],
        "model_errors": [response.error for response in responses],
        "model_evidence_ids": [response.evidence_id for response in responses],
        "model_binding_attempt": binding_attempt,
        "history_isolated": history_denial.get("reason") == "unauthorized_history_read",
        "updater_submit_denied": updater_denial.get("reason") == "unauthorized_action_submit",
        "events": ledger.event_names(),
        "model_summary": runner.summary(),
    }
