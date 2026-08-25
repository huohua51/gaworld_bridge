"""Orchestrate Focused / Full / Drop-trust / No-history cells."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_rel1.probes import leak_tokens, variant_spec
from gaworld.comm.trust import TrustLedger

ObserverFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
UpdaterFn = Callable[[list[dict[str, Any]], list[dict[str, Any]], str, str], dict[str, Any]]
DispatcherFn = Callable[[dict[str, Any] | None, list[dict[str, Any]] | None, str], dict[str, Any]]


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def _rank(version: str) -> int:
    text = str(version or "").strip().lower()
    if text.startswith("v") and text[1:].isdigit():
        return int(text[1:])
    return -1


def _latest_trust(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not messages:
        return None
    return max(messages, key=lambda item: _rank(str(item.get("trust_version") or "")))


def _phase(
    *,
    channel: TrustLedger,
    task_id: str,
    track: str,
    round_name: str,
    version: str,
    spec: dict[str, Any],
    events: list[str],
    updater_fn: UpdaterFn,
    dispatcher_fn: DispatcherFn,
    counters: dict[str, int],
    visible: list[str],
    drop: bool,
) -> dict[str, Any]:
    verified_msg = None
    action_payload: dict[str, Any] = {}
    adopt = None
    submit = None
    trusted_person = spec["formation_person"] if round_name == "formation" else spec["update_person"]
    trusted_state = spec["formation_state"] if round_name == "formation" else spec["update_state"]
    other_person = spec["other_person_formation"] if round_name == "formation" else spec["other_person_update"]

    if track == "focused":
        seeded = channel.seed_focused(
            task_id,
            trusted_person_id=trusted_person,
            trusted_state=trusted_state,
            version=version,
            other_person_id=other_person,
            round_name=round_name,
        )
        events.extend([f"focused_trust_{round_name}", "trust_delivered"])
        if round_name == "update":
            events.append("trust_updated")
        verified_msg = seeded.get("message")
        inbox = channel.read_inbox(task_id, "dispatcher")
        events.append("trust_message_read")
        counters["dispatcher_calls"] += 1
        visible.append(str(verified_msg))
        action_payload = dispatcher_fn(verified_msg, None, round_name)
        if verified_msg and action_payload:
            adopt = channel.adopt_trust(task_id, verified_msg["message_id"])
            if adopt.get("ok") or adopt.get("reason") == "trust_already_adopted":
                events.append("trust_state_adopted")
    elif track == "no_history":
        delivered = channel.deliver_current(task_id, to_role="dispatcher")
        currents = delivered.get("messages") or list(channel._current.get(task_id) or [])
        history = channel.read_history(task_id, "trust_updater")
        counters["updater_calls"] += 1
        proposed = updater_fn(history.get("rounds") or [], currents, version, round_name)
        emitted = channel.emit_trust(task_id, updater_id=2, payload=proposed or {}, round_name=round_name)
        if emitted.get("reason") == "history_not_available":
            events.append("history_not_available")
        counters["dispatcher_calls"] += 1
        visible.append(str(currents))
        action_payload = dispatcher_fn(None, currents, round_name)
        events.append("current_to_dispatcher")
    else:
        if round_name == "formation":
            delivered_cur = channel.deliver_current(task_id)
            if delivered_cur.get("ok"):
                events.append("current_signal_delivered")
            inbox_cur = channel.read_current_inbox(task_id, "trust_updater")
            if inbox_cur.get("ok"):
                events.append("trust_requested")
            currents = inbox_cur.get("messages") or []
        else:
            inbox_cur = channel.read_current_inbox(task_id, "trust_updater")
            currents = inbox_cur.get("messages") or []
            events.append("trust_requested")
        history = channel.read_history(task_id, "trust_updater")
        if history.get("ok"):
            events.append("history_read")
        counters["updater_calls"] += 1
        proposed = updater_fn(history.get("rounds") or [], currents, version, round_name)
        emitted = channel.emit_trust(task_id, updater_id=2, payload=proposed or {}, round_name=round_name)
        if emitted.get("ok"):
            events.append("trust_message_emitted")
            verified_msg = emitted.get("message")
            if round_name == "update":
                formed = spec["formation_person"]
                if verified_msg and verified_msg.get("trusted_person_id") == formed:
                    events.append("trust_not_updated")
                elif verified_msg and verified_msg.get("trusted_person_id") == spec["update_person"]:
                    events.append("trust_updated")
        delivered = None
        if emitted.get("ok"):
            delivered = channel.deliver_trust(task_id, drop=drop)
            if delivered.get("ok") and drop:
                events.append("trust_dropped")
            elif delivered.get("ok"):
                events.append("trust_delivered")
        inbox = channel.read_inbox(task_id, "dispatcher")
        events.append("trust_message_read")
        messages = inbox.get("messages") or []
        latest = _latest_trust(messages)
        if latest and not drop:
            verified_msg = latest
            counters["dispatcher_calls"] += 1
            visible.append(str(verified_msg))
            action_payload = dispatcher_fn(verified_msg, None, round_name)
            adopt = channel.adopt_trust(task_id, verified_msg["message_id"])
            if adopt.get("ok") or adopt.get("reason") == "trust_already_adopted":
                events.append("trust_state_adopted")
        else:
            counters["dispatcher_calls"] += 1
            visible.append("no_trust_message")
            action_payload = dispatcher_fn(None, None, round_name)
            if drop:
                counters["dispatcher_calls"] += 1
                action_payload = dispatcher_fn(None, None, round_name) or action_payload
                events.append("dispatcher_retry_without_trust")

    if action_payload:
        action_payload.setdefault("round", round_name)
        submit = channel.submit_action(task_id, dispatcher_id=3, payload=action_payload)
        if submit.get("ok"):
            events.append("action_submitted")
            action_payload = submit.get("action") or action_payload

    return {"trust": verified_msg, "action": action_payload, "adopt": adopt, "submit": submit}


def run_cell_loop(
    *,
    probe: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    observer_fn: ObserverFn,
    updater_fn: UpdaterFn,
    dispatcher_fn: DispatcherFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "trust.jsonl"
    if ledger_path.exists():
        ledger_path.unlink()
    channel = TrustLedger(str(ledger_path))
    spec = variant_spec(probe, variant)
    events: list[str] = []
    counters = {"observer_calls": 0, "updater_calls": 0, "dispatcher_calls": 0}
    visible: list[str] = []

    channel.bind_agent(task_id, {"relationships": {}, "current_day": 1})
    if track != "no_history":
        channel.put_history(task_id, "trust_updater", spec["history"])
    else:
        channel.put_history(task_id, "trust_updater", [])
    channel.put_private(task_id, "dispatcher", {"rule": probe["rule"], "action": probe["action"]})

    if track != "focused":
        counters["observer_calls"] += 1
        sent = observer_fn(spec["signals"])
        events.append("observation_created")
        for item in sent or []:
            out = channel.send_current(task_id, observer_id=1, message=item)
            if out.get("ok"):
                events.append("current_signal_sent")

    drop = track == "drop_trust"
    formation = _phase(
        channel=channel,
        task_id=task_id,
        track=track,
        round_name="formation",
        version=spec["formation_version"],
        spec=spec,
        events=events,
        updater_fn=updater_fn,
        dispatcher_fn=dispatcher_fn,
        counters=counters,
        visible=visible,
        drop=drop,
    )

    if track not in {"no_history", "focused"}:
        appended = channel.append_outcome(task_id, "trust_updater", spec["reversal"])
        if appended.get("ok"):
            events.append("outcome_appended")
    elif track == "focused":
        events.append("outcome_appended")

    update = _phase(
        channel=channel,
        task_id=task_id,
        track=track,
        round_name="update",
        version=spec["update_version"],
        spec=spec,
        events=events,
        updater_fn=updater_fn,
        dispatcher_fn=dispatcher_fn,
        counters=counters,
        visible=visible,
        drop=drop,
    )

    leak = _contains("\n".join(visible), leak_tokens(probe)) if track == "drop_trust" else []
    dispatcher_read_history = any(
        d.get("reason") == "unauthorized_history_read" and d.get("role") == "dispatcher"
        for d in channel.denials()
    )
    updater_submitted = any(
        d.get("reason") == "unauthorized_action_submit" and d.get("role") == "trust_updater"
        for d in channel.denials()
    )
    rel = channel.relationships_of(task_id)
    inbox_after = channel.read_inbox(task_id, "dispatcher").get("messages") or []
    return {
        "events": events,
        "channel": channel,
        "spec": spec,
        "formation": formation,
        "update": update,
        "formation_trust": formation.get("trust"),
        "update_trust": update.get("trust"),
        "formation_action": formation.get("action") or {},
        "update_action": update.get("action") or {},
        "observer_calls": counters["observer_calls"],
        "updater_calls": counters["updater_calls"],
        "dispatcher_calls": counters["dispatcher_calls"],
        "inbox_empty": not inbox_after,
        "leak_on_drop": leak,
        "dispatcher_read_history": dispatcher_read_history,
        "updater_submitted": updater_submitted,
        "relationships": rel,
        "oracle_formation": spec["formation_value"],
        "oracle_update": spec["update_value"],
        "expected_formation_version": spec["formation_version"],
        "expected_update_version": spec["update_version"],
    }
