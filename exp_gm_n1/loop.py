"""Source → Relay → DecisionMaker. Direct injects verified state; Drop discards Relay output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_n1.budget import BudgetMeter
from exp_gm_n1.contract import decision_contract, parse_json_object, relay_contract, source_contract
from exp_gm_n1.loader import leak_tokens_for, source_private
from exp_gm_n1.prompts import decision_prompt, relay_prompt, source_prompt
from gaworld.comm.relay import RelayChannel

GenerateFn = Callable[[str], str]


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def run_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    source_fn: GenerateFn,
    relay_fn: GenerateFn,
    decision_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel_path = out_dir / "relay.jsonl"
    if channel_path.exists():
        channel_path.unlink()
    channel = RelayChannel(str(channel_path))
    budget = BudgetMeter()
    events: list[str] = []
    private = source_private(task, variant)
    plan = dict(task["plan"])
    channel.put_private(task_id, "observer", private)
    channel.put_private(task_id, "verifier", {"trusted_source_id": task["source_id"]})
    leaks = leak_tokens_for(task, "intervention")

    first_prompt = source_prompt(private)
    source_text = source_fn(first_prompt) or ""
    source_parsed, source_error = source_contract(parse_json_object(source_text))
    budget.charge("source")
    events.append("source_emitted" if source_error == "ok" else "source_contract_failed")
    if source_error == "ok":
        sent = channel.send_raw(
            task_id,
            observer_id=1,
            message={"source_id": source_parsed["source_id"], "reported_state": source_parsed["reported_state"]},
        )
        if sent.get("ok"):
            events.append("raw_sent")

    channel.deliver_raw(task_id)
    raw_inbox = (channel.read_raw_inbox(task_id, "verifier").get("messages") or [])
    trusted = channel.read_private(task_id, "verifier", "verifier")
    relay_p = relay_prompt(raw_inbox, trusted.get("payload") or {"trusted_source_id": task["source_id"]})
    relay_text = relay_fn(relay_p) or ""
    relay_parsed, relay_error = relay_contract(parse_json_object(relay_text))
    budget.charge("relay")
    events.append("relay_ran")
    emitted = {"ok": False}
    if relay_error == "ok":
        emitted = channel.emit_verified(task_id, verifier_id=2, payload=relay_parsed)
        if emitted.get("ok"):
            events.append("verified_emitted")

    delivered = False
    if track == "direct":
        seeded = channel.seed_focused(
            task_id,
            state=private["reported_state"],
            version=private["state_version"],
            source_id=private["source_id"],
        )
        delivered = bool(seeded.get("ok"))
        events.append("direct_state_seeded" if delivered else "direct_seed_failed")
    elif track == "drop":
        if emitted.get("ok"):
            channel.deliver_verified(task_id, drop=True)
        events.append("verified_dropped")
    elif emitted.get("ok"):
        delivered_msg = channel.deliver_verified(task_id, drop=False)
        delivered = bool(delivered_msg.get("ok"))
        events.append("verified_delivered" if delivered else "verified_not_delivered")
    else:
        events.append("verified_not_emitted")

    peek_source = channel.read_private(task_id, "dispatcher", "observer")
    peek_verifier = channel.read_private(task_id, "dispatcher", "verifier")
    inbox = channel.read_inbox(task_id, "dispatcher").get("messages") or []
    dm_p = decision_prompt(task, plan=plan, inbox=inbox)
    dm_text = decision_fn(dm_p) or ""
    dm_parsed, dm_error = decision_contract(parse_json_object(dm_text))
    budget.charge("decision")
    submit = None
    if dm_error == "ok":
        submit = channel.submit_action(
            task_id,
            dispatcher_id=3,
            payload={
                "action": dm_parsed["action"],
                "value": str(dm_parsed.get("value") or plan[task["target"]]),
                "adopted_state_version": private["state_version"] if inbox else "v1",
                "evidence_message_id": dm_parsed["evidence_message_id"],
            },
        )
        if submit.get("ok"):
            events.append("action_submitted")
    else:
        events.append(dm_error)

    (out_dir / "source_raw.txt").write_text(source_text, encoding="utf-8")
    (out_dir / "relay_raw.txt").write_text(relay_text, encoding="utf-8")
    (out_dir / "decision_raw.txt").write_text(dm_text, encoding="utf-8")
    (out_dir / "source_prompt.txt").write_text(first_prompt, encoding="utf-8")
    (out_dir / "relay_prompt.txt").write_text(relay_p, encoding="utf-8")
    (out_dir / "decision_prompt.txt").write_text(dm_p, encoding="utf-8")
    (out_dir / "call_log.json").write_text(
        json.dumps(
            [
                {"stage": "source", "prompt": first_prompt, "raw_text": source_text, "parsed": source_parsed, "error": source_error},
                {"stage": "relay", "prompt": relay_p, "raw_text": relay_text, "parsed": relay_parsed, "error": relay_error},
                {"stage": "decision", "prompt": dm_p, "raw_text": dm_text, "parsed": dm_parsed, "error": dm_error},
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    oracle_marks = [tok for tok in ("n1_bridge_status_001.json", "n1_ferry_status_001.json", "n1_warehouse_gate_001.json") if tok in first_prompt + relay_p + dm_p]
    return {
        "events": events,
        "track": track,
        "variant": variant,
        "source": source_parsed,
        "relay": relay_parsed,
        "decision": dm_parsed,
        "inbox": inbox,
        "plan": plan,
        "private": private,
        "source_error": source_error,
        "relay_error": relay_error,
        "contract_error": dm_error,
        "contract_ok": dm_error == "ok" and source_error == "ok" and relay_error == "ok",
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "relay_ran": True,
        "executor_saw_message": bool(inbox),
        "peek_source": peek_source,
        "peek_verifier": peek_verifier,
        "first_prompt": first_prompt,
        "relay_prompt": relay_p,
        "decision_prompt": dm_p,
        "source_raw": source_text,
        "relay_raw": relay_text,
        "decision_raw": dm_text,
        "leak_on_source_control": _contains(first_prompt, leaks) if variant == "control" else [],
        "drop_dm_leaks": _contains(dm_p, leaks) if track == "drop" else [],
        "oracle_in_prompt": oracle_marks,
        "submit": submit,
        "channel": channel,
    }
