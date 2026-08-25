"""Orchestrate Focused / Full / Drop-verified / No-verification cells."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from holdout_i1.probes import leak_tokens, variant_spec
from holdout_i1.roles import action_contract
from gaworld.comm.relay import RelayChannel

ObserverFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
VerifierFn = Callable[[list[dict[str, Any]], dict[str, Any], str], dict[str, Any]]
DispatcherFn = Callable[[dict[str, Any] | None, list[dict[str, Any]] | None], dict[str, Any]]


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def run_cell_loop(
    *,
    probe: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    observer_fn: ObserverFn,
    verifier_fn: VerifierFn,
    dispatcher_fn: DispatcherFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    relay_path = out_dir / "relay.jsonl"
    if relay_path.exists():
        relay_path.unlink()
    channel = RelayChannel(str(relay_path))
    spec = variant_spec(probe, variant)
    events: list[str] = []
    observer_calls = verifier_calls = dispatcher_calls = 0
    visible: list[str] = []
    verified_msg = None
    raw_for_dispatcher = None
    action_payload = {}
    submit = None
    adopt = None
    contract_error = "empty"

    channel.put_private(task_id, "verifier", {"trusted_source_id": probe["trusted_source_id"]})
    channel.put_private(task_id, "dispatcher", {"rule": probe["rule"], "action": probe["action"]})

    def _observe() -> list[dict[str, Any]]:
        nonlocal observer_calls
        observer_calls += 1
        sent = observer_fn(spec["signals"])
        events.append("observation_created")
        for item in sent or []:
            out = channel.send_raw(task_id, observer_id=1, message=item)
            if out.get("ok"):
                events.append("raw_signal_sent")
        return list(channel._raw.get(task_id) or [])

    if track == "focused":
        seeded = channel.seed_focused(
            task_id, state=spec["trusted_state"], version=spec["state_version"]
        )
        events.extend(["focused_verified", "verified_delivered"])
        verified_msg = seeded.get("message")
        inbox = channel.read_inbox(task_id, "dispatcher")
        events.append("verified_message_read")
        dispatcher_calls += 1
        visible.append(str(verified_msg))
        action_payload = dispatcher_fn(verified_msg, None)
        if verified_msg and action_payload:
            adopt = channel.adopt_verified(task_id, verified_msg["message_id"])
            if adopt.get("ok") or adopt.get("reason") == "verified_already_adopted":
                events.append("verified_state_adopted")
    else:
        raw = _observe()
        if track == "no_verification":
            delivered = channel.deliver_raw_to_dispatcher(task_id)
            raw_for_dispatcher = delivered.get("messages") or raw
            events.append("raw_to_dispatcher")
            dispatcher_calls += 1
            visible.append(str(raw_for_dispatcher))
            action_payload = dispatcher_fn(None, raw_for_dispatcher)
        else:
            delivered_raw = channel.deliver_raw(task_id)
            if delivered_raw.get("ok"):
                events.append("raw_signal_delivered")
            inbox_raw = channel.read_raw_inbox(task_id, "verifier")
            if inbox_raw.get("ok"):
                events.append("verification_requested")
            private = channel.read_private(task_id, "verifier", "verifier")
            verifier_calls += 1
            proposed = verifier_fn(inbox_raw.get("messages") or [], private.get("payload") or {}, spec["state_version"])
            emitted = channel.emit_verified(task_id, verifier_id=2, payload=proposed)
            if emitted.get("ok"):
                events.append("verified_message_emitted")
                verified_msg = emitted.get("message")
            elif emitted.get("reason") == "wrong_source_verified":
                events.append("wrong_source_verified")
            drop = track == "drop_verified"
            if emitted.get("ok"):
                delivered = channel.deliver_verified(task_id, drop=drop)
                if delivered.get("ok") and drop:
                    events.append("verified_dropped")
                elif delivered.get("ok"):
                    events.append("verified_delivered")
            inbox = channel.read_inbox(task_id, "dispatcher")
            events.append("verified_message_read")
            messages = inbox.get("messages") or []
            if messages:
                verified_msg = messages[0]
                dispatcher_calls += 1
                visible.append(str(verified_msg))
                action_payload = dispatcher_fn(verified_msg, None)
                adopt = channel.adopt_verified(task_id, verified_msg["message_id"])
                if adopt.get("ok") or adopt.get("reason") == "verified_already_adopted":
                    events.append("verified_state_adopted")
            else:
                dispatcher_calls += 1
                visible.append("no_verified_message")
                action_payload = dispatcher_fn(None, None)
                if track == "drop_verified":
                    dispatcher_calls += 1
                    action_payload = dispatcher_fn(None, None) or action_payload
                    events.append("dispatcher_retry_without_verified")

    contract_error = "empty"
    if action_payload:
        action_payload, contract_error = action_contract(probe, action_payload)
        if contract_error == "ok":
            submit = channel.submit_action(task_id, dispatcher_id=3, payload=action_payload)
            if submit.get("ok"):
                events.append("action_submitted")
                action_payload = submit.get("action") or action_payload
        else:
            events.append(contract_error)

    leak = _contains("\n".join(visible), leak_tokens(probe)) if track in {"drop_verified"} else []
    # Focused/full may mention source after verification; drop must not see trust table.
    dispatcher_read_trust = any(
        d.get("reason") == "unauthorized_private_read" and d.get("role") == "dispatcher"
        for d in channel.denials()
    )
    verifier_submitted = any(
        d.get("reason") == "unauthorized_action_submit" and d.get("role") == "verifier"
        for d in channel.denials()
    )
    return {
        "events": events,
        "channel": channel,
        "spec": spec,
        "verified": verified_msg,
        "action": action_payload,
        "submit": submit,
        "adopt": adopt,
        "observer_calls": observer_calls,
        "verifier_calls": verifier_calls,
        "dispatcher_calls": dispatcher_calls,
        "inbox_empty": not (channel.read_inbox(task_id, "dispatcher").get("messages") or []),
        "leak_on_drop": leak,
        "dispatcher_read_trust": dispatcher_read_trust,
        "verifier_submitted": verifier_submitted,
        "oracle_value": spec["oracle_value"],
        "expected_version": spec["state_version"],
        "contract_error": contract_error,
    }
