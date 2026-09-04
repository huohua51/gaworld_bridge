"""Replay one frozen review through AgentSociety 2's native social mailbox."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
# AgentSociety2 validates LLM credentials while importing its top-level package,
# even when only the local SimpleSocialSpace is used.  Pin the adapter process to
# a non-routable local endpoint and a sentinel credential so this offline replay
# cannot spend a real key that may exist in the parent shell.
os.environ["AGENTSOCIETY_LLM_API_KEY"] = "offline-replay-no-api-call"
os.environ["AGENTSOCIETY_LLM_API_BASE"] = "http://127.0.0.1:9"

import agentsociety2
from agentsociety2.contrib.env import SimpleSocialSpace

from cross_platform.t3_noncode_replay_v2.protocol import (
    canonical_json,
    expected_executor,
    payload_sha256,
    registered_proposal,
)

PLATFORM = "AgentSociety2"
FIXED_START = datetime(2026, 9, 4, 0, 0, tzinfo=timezone.utc)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows
        ),
        encoding="utf-8",
    )


async def _identity_binding_probe() -> dict[str, Any]:
    """Test the public tool boundary without pretending it has caller context."""

    env = SimpleSocialSpace([(1, "reviewer"), (2, "executor")])
    await env.init(FIXED_START)
    marker = "benchmark-private-marker"
    await env.send_message(sender_id=1, receiver_id=1, content=marker)

    # The public receive tool accepts only a claimed agent_id.  It receives no
    # authenticated caller identity, so a different actor can present id=1.
    observed = await env.receive_messages(agent_id=1)
    accepted = any(message.get("content") == marker for message in observed.messages)
    history = env.get_tool_call_history()
    await env.close()
    return {
        "surface": "SimpleSocialSpace.receive_messages",
        "caller_identity_argument_present": False,
        "claimed_agent_id": 1,
        "cross_actor_read_accepted": accepted,
        "native_acl_enforced_at_tested_boundary": not accepted,
        "tool_call_history": history,
    }


async def _replay_async(
    task: dict[str, Any],
    variant: str,
    review: dict[str, Any] | None,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    trace_path = out_dir / "agentsociety_replay_trace.jsonl"
    history_path = out_dir / "agentsociety_tool_history.jsonl"
    receipt_path = out_dir / "agentsociety_receipts.json"
    final_path = out_dir / "final_state.json"
    manifest_path = out_dir / "replay_manifest.json"

    env = SimpleSocialSpace([(1, "reviewer"), (2, "executor"), (3, "result-sink")])
    await env.init(FIXED_START)

    envelope = {
        "event_kind": "ReviewDelivered" if review is not None else "ReviewUnavailable",
        "task_id": str(task["id"]),
        "variant": variant,
        "proposal": registered_proposal(task),
        "review": review,
    }
    envelope_text = canonical_json(envelope)
    await env.send_message(
        sender_id=1,
        receiver_id=2,
        content=envelope_text,
    )
    executor_receipt = await env.receive_messages(agent_id=2)
    received_messages = list(executor_receipt.messages)
    received_envelope: dict[str, Any] | None = None
    if len(received_messages) == 1:
        try:
            candidate = json.loads(str(received_messages[0].get("content") or ""))
        except (TypeError, ValueError, json.JSONDecodeError):
            candidate = None
        if isinstance(candidate, dict):
            received_envelope = candidate

    delivered_review = None
    if isinstance(received_envelope, dict) and isinstance(
        received_envelope.get("review"), dict
    ):
        delivered_review = dict(received_envelope["review"])
    executor_output = expected_executor(task, delivered_review)
    final_envelope = {
        "event_kind": "FinalStateSubmitted",
        "task_id": str(task["id"]),
        "executor_output": executor_output,
    }
    await env.send_message(
        sender_id=2,
        receiver_id=3,
        content=canonical_json(final_envelope),
    )
    sink_receipt = await env.receive_messages(agent_id=3)
    sink_messages = list(sink_receipt.messages)
    tool_history = env.get_tool_call_history()
    await env.close()

    identity_probe = await _identity_binding_probe()
    source_message_ok = bool(
        len(received_messages) == 1
        and received_messages[0].get("sender_id") == 1
        and received_messages[0].get("content") == envelope_text
    )
    final_message_ok = bool(
        len(sink_messages) == 1
        and sink_messages[0].get("sender_id") == 2
        and sink_messages[0].get("content") == canonical_json(final_envelope)
    )
    trace_rows = [
        {
            "event": "review_received"
            if delivered_review is not None
            else "review_unavailable",
            "task_id": str(task["id"]),
            "variant": variant,
            "ingress_envelope_sha256": payload_sha256(envelope),
            "received_envelope_sha256": payload_sha256(received_envelope),
            "delivered_review_sha256": payload_sha256(delivered_review),
            "native_sender_receiver_verified": source_message_ok,
        },
        {
            "event": "final_state_submitted",
            "task_id": str(task["id"]),
            "executor_output_sha256": payload_sha256(executor_output),
            "native_sender_receiver_verified": final_message_ok,
        },
    ]
    _write_jsonl(trace_path, trace_rows)
    _write_jsonl(history_path, tool_history)
    _write_json(
        receipt_path,
        {"executor": received_messages, "result_sink": sink_messages},
    )
    _write_json(final_path, executor_output)

    try:
        distribution_version = importlib.metadata.version("agentsociety2")
    except importlib.metadata.PackageNotFoundError:
        distribution_version = "unknown"
    result = {
        "run_id": f"t3ncr3_{task['id']}_{variant}_agentsociety2",
        "platform": PLATFORM,
        "environment_version": f"agentsociety2-{distribution_version}",
        "package_dunder_version": str(getattr(agentsociety2, "__version__", "unknown")),
        "execution_surface": "SimpleSocialSpace.send_message/receive_messages",
        "offline_runtime": {
            "credential_mode": "benchmark_sentinel_not_user_secret",
            "api_base": "http://127.0.0.1:9",
            "new_model_calls": 0,
        },
        "trace_version": "shared-review-replay-v3-agentsociety-extension",
        "trace_path": str(trace_path),
        "tool_history_path": str(history_path),
        "receipt_path": str(receipt_path),
        "final_path": str(final_path),
        "ingress_review": review,
        "ingress_review_sha256": payload_sha256(review),
        "delivered_review": delivered_review,
        "delivered_review_sha256": payload_sha256(delivered_review),
        "executor_output": executor_output,
        "proposal_delivered": received_envelope is not None,
        "review_delivery_verified": delivered_review is not None,
        "review_adoption_verified": delivered_review is not None,
        "final_submission_verified": final_message_ok,
        "payload_exact": delivered_review == review,
        "native_sender_receiver_verified": source_message_ok and final_message_ok,
        "native_message_id_observable_at_receive_boundary": bool(
            received_messages and "message_id" in received_messages[0]
        ),
        "native_tool_calls": len(tool_history),
        "verified_receipts": len(received_messages) + len(sink_messages),
        "events": [row["event"] for row in trace_rows],
        "identity_binding_probe": identity_probe,
    }
    _write_json(manifest_path, result)
    return result


def replay(
    task: dict[str, Any],
    variant: str,
    review: dict[str, Any] | None,
    out_dir: Path,
) -> dict[str, Any]:
    return asyncio.run(_replay_async(task, variant, review, out_dir))


__all__ = ["PLATFORM", "replay"]
