"""REL1-v2 five-call full workflow with platform-bound dispatcher evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from exp_rel1_02.loader import current_signals, history_for, latest_row
from v0_first_batch.paths import ensure_import_paths

ensure_import_paths()
from gaworld.comm.trust import TrustLedger


def _prompt(payload: dict[str, Any]) -> str:
    common = [
        "模型不得输出或编造 message_id、trust_version、evidence_message_id；这些绑定字段由平台签发。",
        "只使用本消息中实际送达的证据。",
    ]
    if payload["stage"] == "trust_update":
        common.extend(
            [
                "formation：逐行比较每个来源的 report 与 outcome，按正确行数选择唯一最高者。",
                "formation 的 evidence_row_ids 必须列出所选来源 report==outcome 的全部行。",
                "update：latest_is_binding=true，只使用按输入顺序最后一行；忽略更早累计多数。",
                "update 选择最后一行中 report==outcome 的来源，evidence_row_ids 只能含最后一行 row_id。",
                "trusted_state 必须取 current_signals 中所选来源当前报告；other_source_id 是另一来源。",
                "来源的出现顺序没有优先含义。",
            ]
        )
    elif payload["stage"] == "dispatch":
        common.extend(
            [
                "根据 delivered_trust_message.trusted_state 在 state_to_value 中精确查表。",
                "只选择 selected_value；动作名、消息证据、版本和轮次由平台绑定。",
            ]
        )
    return json.dumps(
        {
            "protocol": "gaworld-benchmark-rel1-registered-reliability-v2",
            "instruction": "只返回一个严格匹配 response_schema 的 JSON 对象；不要使用 Markdown，不要增加字段。",
            "registered_rules": common,
            **payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _observer_validator(expected_people: set[str], states: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        if set(payload) != {"signals"} or not isinstance(payload.get("signals"), list):
            return ["observer_schema_invalid"]
        signals = payload["signals"]
        if len(signals) != 2 or any(set(item) != {"person_id", "reported_state"} for item in signals if isinstance(item, dict)):
            return ["signals_schema_invalid"]
        if {item.get("person_id") for item in signals} != expected_people:
            return ["signal_people_invalid"]
        if any(item.get("reported_state") not in states for item in signals):
            return ["signal_state_invalid"]
        return []

    return validator


def _updater_validator(people: set[str], states: set[str], row_ids: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        errors = []
        expected = {"trusted_source_id", "trusted_state", "other_source_id", "evidence_row_ids"}
        if set(payload) != expected:
            errors.append("updater_schema_invalid")
        if payload.get("trusted_source_id") not in people or payload.get("other_source_id") not in people:
            errors.append("source_id_invalid")
        if payload.get("trusted_source_id") == payload.get("other_source_id"):
            errors.append("sources_must_differ")
        if payload.get("trusted_state") not in states:
            errors.append("trusted_state_invalid")
        evidence = payload.get("evidence_row_ids")
        if not isinstance(evidence, list) or not evidence or any(item not in row_ids for item in evidence):
            errors.append("evidence_rows_invalid")
        return errors

    return validator


def _dispatcher_validator(legal_values: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        if set(payload) != {"selected_value"}:
            return ["dispatcher_schema_invalid"]
        if payload.get("selected_value") not in legal_values:
            return ["selected_value_invalid"]
        return []

    return validator


def _call(
    runner: RecordedModelRunner,
    payload: dict[str, Any],
    *,
    role: str,
    validator: Any,
) -> StructuredModelResponse:
    return runner.call_json(
        _prompt(payload),
        task="benchmark_rel1_v2",
        agent_id=role,
        validator=validator,
    )


def _updater_call(
    runner: RecordedModelRunner,
    task: dict[str, Any],
    history: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    phase: str,
) -> StructuredModelResponse:
    people = {item["person_id"] for item in signals}
    states = {item["reported_state"] for item in signals}
    row_ids = {row["row_id"] for row in history}
    return _call(
        runner,
        {
            "stage": "trust_update",
            "role": "trust_updater",
            "phase": phase,
            "latest_is_binding": True,
            "history_rows_in_order": history,
            "current_signals": signals,
            "response_schema": {
                "trusted_source_id": "source_id",
                "trusted_state": "current_reported_state",
                "other_source_id": "other_source_id",
                "evidence_row_ids": ["row_id"],
            },
        },
        role="trust_updater",
        validator=_updater_validator(people, states, row_ids),
    )


def _dispatch_call(
    runner: RecordedModelRunner,
    task: dict[str, Any],
    trust_message: dict[str, Any] | None,
    phase: str,
) -> StructuredModelResponse:
    return _call(
        runner,
        {
            "stage": "dispatch",
            "role": "dispatcher",
            "phase": phase,
            "delivered_trust_message": trust_message,
            "state_to_value": task["state_to_value"],
            "legal_values": task["legal_values"],
            "response_schema": {"selected_value": "registered_business_value"},
        },
        role="dispatcher",
        validator=_dispatcher_validator(set(task["legal_values"])),
    )


def _platform_trust_payload(response: StructuredModelResponse, version: str) -> dict[str, Any]:
    if not response.ok:
        return {}
    parsed = response.parsed
    return {
        "trusted_person_id": parsed["trusted_source_id"],
        "trusted_state": parsed["trusted_state"],
        "trust_version": version,
        "other_person_id": parsed["other_source_id"],
        "evidence_count": len(parsed["evidence_row_ids"]),
    }


def run_cell(
    task: dict[str, Any],
    variant: str,
    out_dir: Path,
    runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = TrustLedger(str(out_dir / "trust_trace.jsonl"))
    task_id = f"{task['id']}_{variant}_s0"
    signals_expected = current_signals(task)
    initial_history = history_for(task, variant)
    latest = latest_row(task, variant)
    people = {item["person_id"] for item in signals_expected}
    states = {item["reported_state"] for item in signals_expected}
    responses: list[StructuredModelResponse] = []
    ledger.bind_agent(task_id, {"relationships": {}, "current_day": 1})
    ledger.put_history(task_id, "trust_updater", initial_history)
    ledger.put_private(
        task_id,
        "dispatcher",
        {
            "action": task["action"],
            "legal_values": task["legal_values"],
            "state_to_value": task["state_to_value"],
        },
    )

    observer = _call(
        runner,
        {
            "stage": "observe",
            "role": "observer",
            "registered_current_signals": signals_expected,
            "response_schema": {"signals": [{"person_id": "source_id", "reported_state": "state"}]},
        },
        role="observer",
        validator=_observer_validator(people, states),
    )
    responses.append(observer)
    observed = list(observer.parsed.get("signals") or []) if observer.ok else []
    for item in observed:
        ledger.send_current(task_id, observer_id=1, message=item)
    delivered_current = ledger.deliver_current(task_id)
    signals = ledger.read_current_inbox(task_id, "trust_updater").get("messages") or []

    formation_response = _updater_call(runner, task, initial_history, signals, "formation")
    responses.append(formation_response)
    formation_emit = ledger.emit_trust(
        task_id,
        updater_id=2,
        payload=_platform_trust_payload(formation_response, "v1"),
        round_name="formation",
    )
    formation_delivery = ledger.deliver_trust(task_id) if formation_emit.get("ok") else {"ok": False}
    formation_message = formation_emit.get("message") if formation_delivery.get("ok") else None
    formation_adopt = (
        ledger.adopt_trust(task_id, formation_message["message_id"])
        if formation_message
        else {"ok": False}
    )
    formation_dispatch = _dispatch_call(runner, task, formation_message, "formation")
    responses.append(formation_dispatch)
    formation_submit = (
        ledger.submit_bound_action(
            task_id,
            dispatcher_id=3,
            message_id=formation_message["message_id"],
            selected_value=str(formation_dispatch.parsed["selected_value"]),
            round_name="formation",
        )
        if formation_message and formation_dispatch.ok
        else {"ok": False}
    )

    ledger.append_outcome(task_id, "trust_updater", latest)
    update_history = ledger.read_history(task_id, "trust_updater").get("rounds") or []
    update_response = _updater_call(runner, task, update_history, signals, "update")
    responses.append(update_response)
    update_emit = ledger.emit_trust(
        task_id,
        updater_id=2,
        payload=_platform_trust_payload(update_response, "v2"),
        round_name="update",
    )
    update_delivery = ledger.deliver_trust(task_id) if update_emit.get("ok") else {"ok": False}
    update_message = update_emit.get("message") if update_delivery.get("ok") else None
    update_adopt = (
        ledger.adopt_trust(task_id, update_message["message_id"])
        if update_message
        else {"ok": False}
    )
    update_dispatch = _dispatch_call(runner, task, update_message, "update")
    responses.append(update_dispatch)
    update_submit = (
        ledger.submit_bound_action(
            task_id,
            dispatcher_id=3,
            message_id=update_message["message_id"],
            selected_value=str(update_dispatch.parsed["selected_value"]),
            round_name="update",
        )
        if update_message and update_dispatch.ok
        else {"ok": False}
    )

    history_denial = ledger.read_history(task_id, "dispatcher")
    submit_denial = ledger.reject_submit(task_id, "trust_updater")
    outputs = [response.parsed for response in responses]
    forbidden_keys = {"message_id", "trust_version", "evidence_message_id", "adopted_trust_version", "action"}
    model_binding_attempt = any(isinstance(payload, dict) and forbidden_keys & set(payload) for payload in outputs)
    return {
        "task_id": task["id"],
        "variant": variant,
        "observed_signals": observed,
        "delivered_current": delivered_current,
        "formation_model": formation_response.parsed,
        "formation_message": formation_message,
        "formation_adopt": formation_adopt,
        "formation_action": formation_submit.get("action") or {},
        "update_model": update_response.parsed,
        "update_message": update_message,
        "update_adopt": update_adopt,
        "update_action": update_submit.get("action") or {},
        "relationships": ledger.relationships_of(task_id),
        "model_ok": [response.ok for response in responses],
        "model_errors": [response.error for response in responses],
        "model_evidence_ids": [response.evidence_id for response in responses],
        "model_binding_attempt": model_binding_attempt,
        "history_isolated": history_denial.get("reason") == "unauthorized_history_read",
        "updater_submit_denied": submit_denial.get("reason") == "unauthorized_action_submit",
        "events": ledger.event_names(),
        "denials": ledger.denials(),
        "model_summary": runner.summary(),
    }
