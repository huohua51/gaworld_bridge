"""Execute a deterministic T4-v2 registered-transport cell."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gaworld.comm.network import NetworkPropagationChannel

from exp_gm_t4_02.loader import payload_for


def _edges(route: list[str]) -> list[tuple[str, str]]:
    return [(route[index], route[index + 1]) for index in range(len(route) - 1)]


def run_cell(
    task: dict[str, Any], variant: str, track: str, out_dir: Path
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    route = [str(node) for node in task["path"]]
    bridge = tuple(str(node) for node in task["bridge"])
    trace_path = out_dir / "network_trace.jsonl"
    channel = NetworkPropagationChannel(str(trace_path), _edges(route))
    message_id = str(task["message_id"])
    payload = payload_for(task, variant)

    intervention = None
    if track == "remove_bridge":
        intervention = channel.remove_edge(
            *bridge, intervention_id=f"remove-{task['id']}-bridge"
        )

    injected = channel.inject(
        message_id=message_id,
        source_id=str(task["source"]),
        state_version=str(task["state_version"]),
        payload=payload,
    )
    deliveries: list[dict[str, Any]] = []
    for sender, receiver in _edges(route):
        drop = track == "drop_bridge" and (sender, receiver) == bridge
        delivered = channel.deliver(message_id, sender, receiver, drop=drop)
        deliveries.append({"sender": sender, "receiver": receiver, **delivered})
        if not delivered.get("ok") or delivered.get("dropped"):
            break
        accepted = channel.accept(message_id, receiver)
        if not accepted.get("ok"):
            break

    target = str(task["target"])
    target_received = channel.received_by(message_id, target)
    target_accepted = channel.accepted_by(message_id, target)
    adopted = target_received and target_accepted
    action_name = str(payload["target_action"]) if adopted else "keep_current"
    submitted = channel.submit_action(
        target,
        action_name,
        message_id=message_id if adopted else None,
    )

    return {
        "trace_path": str(trace_path),
        "trace_nonempty": trace_path.is_file() and trace_path.stat().st_size > 0,
        "track": track,
        "variant": variant,
        "message_id": message_id,
        "message_class": task["message_class"],
        "transport_rule": "always_forward_registered_update",
        "payload": payload,
        "injected": injected,
        "intervention": intervention,
        "deliveries": deliveries,
        "target_received": target_received,
        "target_accepted": target_accepted,
        "path_to_target": channel.path_to(message_id, target),
        "action": submitted.get("action") or {},
        "action_submit": submitted,
        "events": channel.event_names(),
        "denials": channel.denials(),
        "bridge_active": channel.edge_active(*bridge),
    }
