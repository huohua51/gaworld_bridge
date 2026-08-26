"""Model-driven T4 receive, accept, forward and target-action loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaworld.comm.network import NetworkPropagationChannel

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse


def _edges(route: list[str]) -> list[tuple[str, str]]:
    return [(route[index], route[index + 1]) for index in range(len(route) - 1)]


def _prompt(
    *,
    role: str,
    node_id: str,
    message: dict[str, Any] | None,
    next_node: str | None,
    allowed_actions: list[str],
) -> str:
    schemas = {
        "source": {"forward": "boolean", "reason": "string"},
        "intermediate": {"accept": "boolean", "forward": "boolean", "reason": "string"},
        "target": {"accept": "boolean", "target_action": "string", "reason": "string"},
    }
    return json.dumps(
        {
            "protocol": "gaworld-benchmark-t4-model-v1",
            "instruction": (
                "Return exactly one JSON object matching response_schema. "
                "Do not use markdown or add fields. Use only received evidence."
            ),
            "task_family": "T4",
            "role": role,
            "node_id": node_id,
            "message_received": message is not None,
            "message": message,
            "next_registered_node": next_node,
            "allowed_target_actions": allowed_actions,
            "response_schema": schemas[role],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate(role: str, allowed_actions: set[str]):
    expected_keys = {
        "source": {"forward", "reason"},
        "intermediate": {"accept", "forward", "reason"},
        "target": {"accept", "target_action", "reason"},
    }[role]

    def validator(payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if set(payload) != expected_keys:
            errors.append(f"keys_must_equal:{sorted(expected_keys)}")
        for field in {"accept", "forward"} & expected_keys:
            if not isinstance(payload.get(field), bool):
                errors.append(f"{field}_must_be_boolean")
        if (
            not isinstance(payload.get("reason"), str)
            or not payload.get("reason", "").strip()
        ):
            errors.append("reason_must_be_nonempty_string")
        if role == "target" and payload.get("target_action") not in allowed_actions:
            errors.append("target_action_not_allowed")
        return errors

    return validator


def _call(
    runner: RecordedModelRunner,
    *,
    role: str,
    node_id: str,
    message: dict[str, Any] | None,
    next_node: str | None,
    allowed_actions: set[str],
) -> StructuredModelResponse:
    return runner.call_json(
        _prompt(
            role=role,
            node_id=node_id,
            message=message,
            next_node=next_node,
            allowed_actions=sorted(allowed_actions),
        ),
        task="benchmark_t4",
        agent_id=node_id,
        validator=_validate(role, allowed_actions),
    )


def run_cell(
    task: dict[str, Any],
    variant: str,
    track: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    route = [str(node) for node in task["path"]]
    bridge = tuple(str(node) for node in task["bridge"])
    trace_path = out_dir / "network_trace.jsonl"
    channel = NetworkPropagationChannel(str(trace_path), _edges(route))
    message_id = str(task["message_id"])
    payload = dict(task[f"{variant}_payload"])
    message = {
        "message_id": message_id,
        "state_version": str(task["state_version"]),
        "payload": payload,
    }
    allowed_actions = {
        "keep_current",
        str(task["intervention_payload"]["target_action"]),
    }

    intervention = None
    if track == "remove_bridge":
        intervention = channel.remove_edge(
            *bridge, intervention_id=f"model-remove-{task['id']}-bridge"
        )
    injected = channel.inject(
        message_id=message_id,
        source_id=str(task["source"]),
        state_version=str(task["state_version"]),
        payload=payload,
    )
    responses: list[StructuredModelResponse] = []
    deliveries: list[dict[str, Any]] = []
    source_response = _call(
        model_runner,
        role="source",
        node_id=route[0],
        message=message,
        next_node=route[1],
        allowed_actions=allowed_actions,
    )
    responses.append(source_response)
    can_forward = bool(source_response.ok and source_response.parsed.get("forward"))
    target_response: StructuredModelResponse | None = None

    for sender, receiver in _edges(route):
        if not can_forward:
            break
        drop = track == "drop_bridge" and (sender, receiver) == bridge
        delivered = channel.deliver(message_id, sender, receiver, drop=drop)
        deliveries.append({"sender": sender, "receiver": receiver, **delivered})
        if not delivered.get("ok") or delivered.get("dropped"):
            break
        if receiver == route[-1]:
            target_response = _call(
                model_runner,
                role="target",
                node_id=receiver,
                message=message,
                next_node=None,
                allowed_actions=allowed_actions,
            )
            responses.append(target_response)
            break
        intermediate = _call(
            model_runner,
            role="intermediate",
            node_id=receiver,
            message=message,
            next_node=route[route.index(receiver) + 1],
            allowed_actions=allowed_actions,
        )
        responses.append(intermediate)
        accepted = bool(intermediate.ok and intermediate.parsed.get("accept"))
        channel.accept(message_id, receiver, accepted=accepted)
        can_forward = bool(accepted and intermediate.parsed.get("forward"))

    target = route[-1]
    target_received = channel.received_by(message_id, target)
    if target_response is None:
        target_response = _call(
            model_runner,
            role="target",
            node_id=target,
            message=None,
            next_node=None,
            allowed_actions=allowed_actions,
        )
        responses.append(target_response)

    submitted: dict[str, Any] = {"ok": False, "reason": "model_response_invalid"}
    if target_response.ok:
        accepted = bool(target_response.parsed["accept"] and target_received)
        if target_received:
            channel.accept(message_id, target, accepted=accepted)
        submitted = channel.submit_action(
            target,
            str(target_response.parsed["target_action"]),
            message_id=message_id if accepted else None,
        )

    return {
        "trace_path": str(trace_path),
        "model_trace_path": str(model_runner.path),
        "trace_nonempty": trace_path.is_file() and trace_path.stat().st_size > 0,
        "track": track,
        "variant": variant,
        "message_id": message_id,
        "payload": payload,
        "injected": injected,
        "intervention": intervention,
        "deliveries": deliveries,
        "target_received": target_received,
        "target_accepted": channel.accepted_by(message_id, target),
        "path_to_target": channel.path_to(message_id, target),
        "action": submitted.get("action") or {},
        "action_submit": submitted,
        "events": channel.event_names(),
        "denials": channel.denials(),
        "bridge_active": channel.edge_active(*bridge),
        "model_call_evidence_ids": [response.evidence_id for response in responses],
        "model_summary": model_runner.summary(),
    }
