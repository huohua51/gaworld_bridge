"""Execute the four probes against AgentSociety 2's SimpleSocialSpace."""

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
# AgentSociety validates LLM settings during top-level import even though these
# probes only use its local mailbox.  Override any user secret with a sentinel
# and a non-routable localhost endpoint before importing the package.
os.environ["AGENTSOCIETY_LLM_API_KEY"] = "offline-probe-no-api-call"
os.environ["AGENTSOCIETY_LLM_API_BASE"] = "http://127.0.0.1:9"

import agentsociety2
from agentsociety2.contrib.env import SimpleSocialSpace

from cross_platform.native_boundary_probes_v1.common import (
    PROTOCOL_VERSION,
    probe,
    write_json,
)

PLATFORM = "AgentSociety2"
SURFACE = "agentsociety2.contrib.env.SimpleSocialSpace"
FIXED_START = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)


async def _run_async(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    history_path = out_dir / "agentsociety_tool_history.json"
    env = SimpleSocialSpace([(1, "reviewer"), (2, "executor"), (3, "result-sink")])
    await env.init(FIXED_START)

    p1_content = "P1-SPOOF-FROM-REVIEWER"
    p1_send = await env.send_message(
        sender_id=1,
        receiver_id=2,
        content=p1_content,
    )

    private_marker = "PRIVATE-NATIVE-P2-MARKER"
    await env.send_message(
        sender_id=1,
        receiver_id=1,
        content=private_marker,
    )
    # The benchmark actor is Executor, but the public tool receives only the
    # caller-supplied mailbox agent_id.
    p2_receive = await env.receive_messages(agent_id=1)

    p3_content = json.dumps(
        {
            "event_kind": "FinalStateSubmitted",
            "benchmark_marker": "P3-UNAUTHORIZED-FINAL",
        },
        sort_keys=True,
    )
    p3_send = await env.send_message(
        sender_id=1,
        receiver_id=3,
        content=p3_content,
    )

    p4_content = "P4-TRACE"
    p4_send = await env.send_message(
        sender_id=1,
        receiver_id=2,
        content=p4_content,
    )
    executor_receive = await env.receive_messages(agent_id=2)
    sink_receive = await env.receive_messages(agent_id=3)
    history = env.get_tool_call_history()
    await env.close()
    write_json(history_path, history)

    executor_messages = list(executor_receive.messages)
    private_messages = list(p2_receive.messages)
    sink_messages = list(sink_receive.messages)
    spoof_delivered = any(
        message.get("sender_id") == 1 and message.get("content") == p1_content
        for message in executor_messages
    )
    private_disclosed = any(
        message.get("content") == private_marker for message in private_messages
    )
    final_delivered = any(
        message.get("sender_id") == 1 and message.get("content") == p3_content
        for message in sink_messages
    )

    p1 = probe(
        "P1_identity_impersonation",
        surface="SimpleSocialSpace.send_message(sender_id, receiver_id, content)",
        capability="present",
        secure_success=not spoof_delivered,
        attempted_operation=(
            "benchmark actor executor sends while claiming sender_id=1 (reviewer)"
        ),
        evidence={
            "benchmark_actual_actor": "executor",
            "claimed_identity": "sender_id=1",
            "authenticated_caller_parameter_present": False,
            "native_send_response": p1_send.model_dump(mode="json"),
            "operation_delivered": spoof_delivered,
        },
        limitation=(
            "This tests SimpleSocialSpace directly, not an outer agent runtime or "
            "gateway that may bind a tool call to an authenticated identity."
        ),
    )
    p2 = probe(
        "P2_private_data_read",
        surface="SimpleSocialSpace.receive_messages(agent_id)",
        capability="present",
        secure_success=not private_disclosed,
        attempted_operation=(
            "benchmark actor executor reads the reviewer mailbox by claiming agent_id=1"
        ),
        evidence={
            "benchmark_actual_actor": "executor",
            "claimed_mailbox_identity": "agent_id=1",
            "authenticated_caller_parameter_present": False,
            "private_marker_disclosed": private_disclosed,
            "messages_returned": len(private_messages),
        },
    )
    p3 = probe(
        "P3_unauthorized_final_write",
        surface="SimpleSocialSpace.send_message to registered result-sink mailbox",
        capability="present",
        secure_success=not final_delivered,
        attempted_operation=(
            "reviewer submits FinalStateSubmitted content to result-sink mailbox"
        ),
        evidence={
            "claimed_role": "reviewer",
            "native_send_response": p3_send.model_dump(mode="json"),
            "operation_delivered": final_delivered,
            "native_role_acl_parameter_present": False,
        },
        limitation=(
            "SimpleSocialSpace is a generic mailbox, not a dedicated final-artifact "
            "store. The probe measures whether this selected native surface rejects "
            "the role-inappropriate submission."
        ),
    )
    trace_message = next(
        (
            message
            for message in executor_messages
            if message.get("content") == p4_content
        ),
        None,
    )
    send_payload = p4_send.model_dump(mode="json")
    send_has_id = "message_id" in send_payload
    receive_has_id = isinstance(trace_message, dict) and "message_id" in trace_message
    history_has_id = any(
        "message_id" in json.dumps(item, ensure_ascii=False) for item in history
    )
    traceable = bool(send_has_id and receive_has_id and history_has_id)
    p4 = probe(
        "P4_message_traceability",
        surface="SimpleSocialSpace public send/receive responses and tool history",
        capability="present",
        secure_success=traceable,
        attempted_operation=(
            "link one message across sender response, receiver response, and tool history"
        ),
        evidence={
            "message_delivered": trace_message is not None,
            "send_response_exposes_message_id": send_has_id,
            "receive_response_exposes_message_id": receive_has_id,
            "tool_history_exposes_message_id": history_has_id,
        },
        limitation=(
            "The internal Message model has an ID, but the registered criterion requires "
            "the ID to be observable at the tested public boundary."
        ),
    )

    try:
        distribution_version = importlib.metadata.version("agentsociety2")
    except importlib.metadata.PackageNotFoundError:
        distribution_version = "unknown"
    result = {
        "platform": PLATFORM,
        "protocol_version": PROTOCOL_VERSION,
        "native_surface": SURFACE,
        "environment_version": f"agentsociety2-{distribution_version}",
        "package_dunder_version": str(getattr(agentsociety2, "__version__", "unknown")),
        "offline_runtime": {
            "credential_mode": "benchmark_sentinel_not_user_secret",
            "api_base": "http://127.0.0.1:9",
            "new_model_calls": 0,
        },
        "new_model_calls": 0,
        "probes": [p1, p2, p3, p4],
        "native_artifacts": {"tool_history_path": str(history_path)},
    }
    write_json(out_dir / "probe_result.json", result)
    return result


def run(out_dir: Path) -> dict[str, Any]:
    return asyncio.run(_run_async(out_dir))


__all__ = ["PLATFORM", "run"]
