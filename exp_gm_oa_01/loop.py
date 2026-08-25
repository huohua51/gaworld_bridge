"""Single-call cell loop. Both protocols see the same current-state event."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_gm_oa_01.channel import ChangeGateChannel
from exp_gm_oa_01.loader import build_notice, registered_plan
from exp_gm_oa_01.prompts import action_contract

AgentFn = Callable[[dict[str, Any] | None, dict[str, Any]], dict[str, Any]]


def run_cell_loop(
    *,
    task: dict[str, Any],
    variant: str,
    protocol: str,
    task_id: str,
    out_dir: Path,
    agent_fn: AgentFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel_path = out_dir / "change_gate.jsonl"
    if channel_path.exists():
        channel_path.unlink()
    channel = ChangeGateChannel(channel_path)
    events: list[str] = []
    action_payload: dict[str, Any] = {}
    submit = None
    contract_error = "empty"
    agent_calls = 0

    channel.register_plan(task_id, registered_plan(task))
    notice = build_notice(task, variant)
    injected = channel.inject_event(task_id, notice)
    if injected.get("ok"):
        events.append("event_injected")
    seeded = channel.seed_notice()
    if seeded.get("ok"):
        events.append("current_state_seeded")
        notice = seeded.get("notice") or notice
    agent_calls += 1
    action_payload = agent_fn(notice, dict(channel.plan))
    if action_payload:
        action_payload, contract_error = action_contract(protocol, action_payload)
        if contract_error == "ok":
            submit = channel.submit_action(task_id, agent_id=1, payload=action_payload, role="agent")
            if submit.get("ok"):
                events.append("action_submitted")
                action_payload = submit.get("action") or action_payload
        elif contract_error == "fields_not_extractable":
            events.append("fields_not_extractable")
        elif contract_error == "empty":
            events.append("empty")
        else:
            events.append(contract_error)

    env_rewrote = channel.environment_mutated or channel.plan_drift_without_agent_revise()
    if env_rewrote:
        events.append("environment_rewrote_plan")
    return {
        "task_id": task_id,
        "events": events,
        "channel": channel,
        "notice": notice,
        "action": action_payload,
        "submit": submit,
        "agent_calls": agent_calls,
        "contract_error": contract_error,
        "injected": channel.injected,
        "plan": dict(channel.plan),
        "initial_plan": dict(channel.initial_plan),
        "env_rewrote": env_rewrote,
        "source_contamination": env_rewrote,
    }
