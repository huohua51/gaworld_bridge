"""direct_household_state / full_family_event / drop_family_event cells."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_gm_02.probes import household_for, initial_schedule, variant_spec
from exp_gm_02.roles import action_contract
from gaworld.life.family import FamilyCareChannel, NONE

AgentFn = Callable[[dict[str, Any] | None, list[dict[str, Any]]], dict[str, Any]]


def run_cell_loop(
    *,
    probe: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    agent_fn: AgentFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel_path = out_dir / "family.jsonl"
    if channel_path.exists():
        channel_path.unlink()
    channel = FamilyCareChannel(str(channel_path))
    spec = variant_spec(probe, variant)
    events: list[str] = []
    notice = None
    action_payload: dict[str, Any] = {}
    submit = None
    adopt = None
    contract_error = "empty"
    agent_calls = 0

    channel.register_household(task_id, household_for(probe))
    channel.set_schedule(task_id, initial_schedule(probe))
    injected = channel.inject_event(
        task_id,
        requires_care=bool(spec["requires_care"]),
        state_version=spec["state_version"],
        patient_id=probe["patient_id"],
        caregiver_id=probe["legal_caregiver_id"],
        slot_id=probe["conflict_slot_id"],
        expense_amount=int(probe["registered_expense"]),
    )
    if injected.get("ok"):
        events.append("care_event_injected")

    if track == "direct_household_state":
        seeded = channel.seed_direct(task_id)
        if seeded.get("ok"):
            events.append("current_state_seeded")
            notice = seeded.get("notice")
        inbox = channel.read_perception(task_id, "agent")
        events.append("perception_read")
        notices = inbox.get("notices") or []
        if notices:
            notice = notices[0]
        agent_calls += 1
        action_payload = agent_fn(notice, channel.schedule_of(task_id))
    else:
        packaged = channel.package_perception(task_id)
        if packaged.get("ok"):
            events.append("perception_packaged")
        drop = track == "drop_family_event"
        delivered = channel.deliver_perception(task_id, drop=drop)
        if delivered.get("ok") and drop:
            events.append("perception_dropped")
        elif delivered.get("ok"):
            events.append("perception_delivered")
        inbox = channel.read_perception(task_id, "agent")
        events.append("perception_read")
        notices = inbox.get("notices") or []
        if notices:
            notice = notices[0]
            agent_calls += 1
            action_payload = agent_fn(notice, channel.schedule_of(task_id))
        else:
            agent_calls += 1
            action_payload = agent_fn(None, channel.schedule_of(task_id))

    if action_payload:
        action_payload, contract_error = action_contract(probe, action_payload)
        if contract_error == "ok":
            submit = channel.submit_action(task_id, agent_id=1, payload=action_payload)
            if submit.get("ok"):
                events.append("action_submitted")
                action_payload = submit.get("action") or action_payload
            elif submit.get("reason") == "fields_not_extractable":
                contract_error = "fields_not_extractable"
            elif submit.get("reason") == "wrong_caregiver_selected":
                events.append("wrong_caregiver_selected")
        elif contract_error == "fields_not_extractable":
            events.append("fields_not_extractable")
        else:
            events.append(contract_error)

    evidence = str((action_payload or {}).get("evidence_event_id") or "")
    if evidence and evidence != NONE:
        adopt = channel.adopt_event(task_id, evidence)
        if adopt.get("ok") or adopt.get("reason") == "event_already_adopted":
            events.append("event_adopted")

    env_assigned = any(d.get("reason") == "environment_assigned_caregiver" for d in channel.denials())
    return {
        "task_id": task_id,
        "events": events,
        "channel": channel,
        "spec": spec,
        "notice": notice,
        "action": action_payload,
        "submit": submit,
        "adopt": adopt,
        "agent_calls": agent_calls,
        "inbox_empty": not channel.inbox_of(task_id),
        "env_assigned": env_assigned,
        "expected_version": spec["state_version"],
        "contract_error": contract_error,
        "injected": channel.injected_of(task_id),
        "schedule": channel.schedule_of(task_id),
        "expenses": channel.expenses_of(task_id),
        "responsibility": channel.responsibility_of(task_id),
    }
