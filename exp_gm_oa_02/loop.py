"""Single-call exclusive-action loop. Tasks are loaded read-only from frozen OA-01."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_gm_oa_01.loader import build_notice, registered_plan
from exp_gm_oa_02.channel import ExclusiveActionChannel
from exp_gm_oa_02.contract import action_contract, is_contract_failure

AgentFn = Callable[[dict[str, Any] | None, dict[str, Any]], dict[str, Any]]


def run_cell_loop(
    *,
    task: dict[str, Any],
    variant: str,
    instance_id: str,
    out_dir: Path,
    agent_fn: AgentFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel_path = out_dir / "exclusive_action.jsonl"
    if channel_path.exists():
        channel_path.unlink()
    channel = ExclusiveActionChannel(channel_path)
    events: list[str] = []
    action_payload: dict[str, Any] = {}
    submit = None
    contract_error = "empty"
    agent_calls = 0

    channel.register_plan(instance_id, registered_plan(task))
    notice = build_notice(task, variant)
    injected = channel.inject_event(instance_id, notice)
    if injected.get("ok"):
        events.append("event_injected")
    seeded = channel.seed_notice()
    if seeded.get("ok"):
        events.append("current_state_seeded")
        notice = seeded.get("notice") or notice
    agent_calls += 1
    raw = agent_fn(notice, dict(channel.plan))
    action_payload, contract_error = action_contract(raw)
    if contract_error == "ok":
        submit = channel.submit_action(instance_id, agent_id=1, payload=raw, role="agent")
        if submit.get("ok"):
            events.append("action_submitted")
            action_payload = submit.get("action") or action_payload
        else:
            contract_error = str(submit.get("reason") or contract_error)
            events.append(contract_error)
    elif contract_error == "fields_not_extractable" or contract_error == "empty":
        events.append(contract_error)
    else:
        submit = channel.submit_action(instance_id, agent_id=1, payload=raw, role="agent")
        events.append(contract_error)

    env_rewrote = channel.environment_mutated or channel.plan_drift_without_agent_revise()
    if env_rewrote:
        events.append("environment_rewrote_plan")
    return {
        "task_id": instance_id,
        "events": events,
        "channel": channel,
        "notice": notice,
        "action": action_payload,
        "raw_action": raw if isinstance(raw, dict) else {},
        "submit": submit,
        "agent_calls": agent_calls,
        "contract_error": contract_error,
        "contract_rejected": is_contract_failure(contract_error),
        "injected": channel.injected,
        "plan": dict(channel.plan),
        "initial_plan": dict(channel.initial_plan),
        "env_rewrote": env_rewrote,
        "source_contamination": env_rewrote,
    }
