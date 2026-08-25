"""direct_current_state / full_event / drop_event cells."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_gm_01.probes import initial_schedule, leak_tokens, variant_spec, venues_for
from exp_gm_01.roles import action_contract
from gaworld.life.venue import VenueEventChannel

AgentFn = Callable[[dict[str, Any] | None, list[dict[str, Any]]], dict[str, Any]]


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def run_cell_loop(
    *,
    probe: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    agent_fn: AgentFn,
    city_map: dict[str, Any],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel_path = out_dir / "venue.jsonl"
    if channel_path.exists():
        channel_path.unlink()
    channel = VenueEventChannel(str(channel_path), city_map=city_map)
    spec = variant_spec(probe, variant)
    events: list[str] = []
    notice = None
    action_payload: dict[str, Any] = {}
    submit = None
    adopt = None
    contract_error = "empty"
    visible: list[str] = []
    agent_calls = 0

    channel.register_venues(
        task_id,
        venues_for(probe),
        origin=probe["origin"],
        required_type=probe["required_type"],
        slot_id=probe["slot_id"],
    )
    channel.set_schedule(task_id, initial_schedule(probe))
    injected = channel.inject_event(
        task_id,
        venue_id=probe["original"],
        status=spec["status"],
        state_version=spec["state_version"],
        slot_id=probe["slot_id"],
    )
    if injected.get("ok"):
        events.append("event_injected")

    if track == "direct_current_state":
        seeded = channel.seed_direct(task_id)
        if seeded.get("ok"):
            events.append("current_state_seeded")
            notice = seeded.get("notice")
        inbox = channel.read_perception(task_id, "agent")
        events.append("perception_read")
        notices = inbox.get("notices") or []
        if notices:
            notice = notices[0]
        visible.append(str(notice))
        agent_calls += 1
        action_payload = agent_fn(notice, channel.schedule_of(task_id))
        evidence = str((action_payload or {}).get("evidence_event_id") or "")
        if notice and evidence:
            adopt = channel.adopt_event(task_id, evidence)
            if adopt.get("ok") or adopt.get("reason") == "event_already_adopted":
                events.append("event_adopted")
    else:
        packaged = channel.package_perception(task_id)
        if packaged.get("ok"):
            events.append("perception_packaged")
        drop = track == "drop_event"
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
            visible.append(str(notice))
            agent_calls += 1
            action_payload = agent_fn(notice, channel.schedule_of(task_id))
            evidence = str((action_payload or {}).get("evidence_event_id") or "")
            if evidence:
                adopt = channel.adopt_event(task_id, evidence)
                if adopt.get("ok") or adopt.get("reason") == "event_already_adopted":
                    events.append("event_adopted")
        else:
            visible.append("no_venue_notice")
            agent_calls += 1
            action_payload = agent_fn(None, channel.schedule_of(task_id))

    if action_payload:
        action_payload, contract_error = action_contract(probe, action_payload)
        if contract_error in {"ok", "destination_not_in_contract", "slot_not_in_contract", "action_not_in_contract"}:
            # Still submit extractable fields so R1 can see an agent payload.
            submit = channel.submit_action(task_id, agent_id=1, payload=action_payload) if contract_error == "ok" else channel.submit_action(
                task_id,
                agent_id=1,
                payload={
                    "action": action_payload.get("action", ""),
                    "destination": action_payload.get("destination", ""),
                    "slot_id": action_payload.get("slot_id", ""),
                    "adopted_state_version": action_payload.get("adopted_state_version", ""),
                    "evidence_event_id": action_payload.get("evidence_event_id", ""),
                },
            )
            if submit.get("ok"):
                events.append("action_submitted")
                action_payload = submit.get("action") or action_payload
            elif submit.get("reason") == "fields_not_extractable":
                contract_error = "fields_not_extractable"
        elif contract_error == "fields_not_extractable":
            events.append("fields_not_extractable")
        else:
            events.append(contract_error)

    env_submit = any(d.get("reason") == "unauthorized_action_submit" for d in channel.denials())
    env_rewrite = any(d.get("reason") == "environment_rewrote_schedule" for d in channel.denials())
    leak = []
    if track == "drop_event":
        blob = "\n".join(visible)
        leak = _contains(blob, leak_tokens(probe, spec))
        event_id = str((channel.injected_of(task_id) or {}).get("event_id") or "")
        if event_id and event_id in blob:
            leak.append("event_id")
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
        "leak_on_drop": leak,
        "env_submitted": env_submit,
        "env_rewrote": env_rewrite,
        "oracle_destination": spec["oracle_destination"],
        "expected_version": spec["state_version"],
        "contract_error": contract_error,
        "injected": channel.injected_of(task_id),
        "schedule": channel.schedule_of(task_id),
    }
