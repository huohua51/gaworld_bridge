"""T4-v2 protocol-parity adapter backed by YuLan-OneSim's EventBus."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# YuLan-OneSim imports the optional visualization stack from EventBus even when
# no graph is rendered. Keep the evaluation venv headless; WorkGraph is not used
# by this adapter.
_pyvis = types.ModuleType("pyvis")
_pyvis.__path__ = []  # type: ignore[attr-defined]
_pyvis_network = types.ModuleType("pyvis.network")
_pyvis_network.Network = object  # type: ignore[attr-defined]
sys.modules["pyvis"] = _pyvis
sys.modules["pyvis.network"] = _pyvis_network

from onesim.events import EndEvent, Event, EventBus

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from exp_gm_t4_02.loader import payload_for
from model_pilot.t4_v2 import _call


@dataclass(frozen=True)
class _Profile:
    agent_type: str


class _Trace:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.seq = 0

    def write(self, event: str, **payload: Any) -> dict[str, Any]:
        self.seq += 1
        row = {"seq": self.seq, "event": event, **payload}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


class _T4Agent:
    def __init__(
        self,
        *,
        node_id: str,
        role: str,
        route_index: int,
        route: list[str],
        bridge: tuple[str, str],
        track: str,
        bus: EventBus,
        trace: _Trace,
        receipt_path: Path,
        message: dict[str, Any],
        allowed_actions: set[str],
        runner: RecordedModelRunner,
    ) -> None:
        self.node_id = node_id
        self.role = role
        self.route_index = route_index
        self.route = route
        self.bridge = bridge
        self.track = track
        self.bus = bus
        self.trace = trace
        self.receipt_path = receipt_path
        self.message = message
        self.allowed_actions = allowed_actions
        self.runner = runner
        self.profile = _Profile({"source": "Source", "intermediate": "Bridge", "target": "Target"}[role])
        self.received: list[Event] = []
        self.responses: list[StructuredModelResponse] = []
        self.target_response: StructuredModelResponse | None = None

    def _receipt(self, event: Event) -> None:
        row = {
            "event_id": event.event_id,
            "event_kind": event.event_kind,
            "parent_event_id": event.parent_event_id,
            "sender_id": str(event.from_agent_id),
            "receiver_id": self.node_id,
            "message_id": self.message["message_id"],
        }
        with self.receipt_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _emit(self, event: Event) -> None:
        # In YuLan single-process mode dispatch_event is exactly queue.put. add_event
        # is synchronous, so put_nowait avoids an untracked background task race.
        self.bus.queue.put_nowait(event)

    def add_event(self, event: Event) -> None:
        self.received.append(event)
        self._receipt(event)
        if self.role != "source":
            self.trace.write(
                "message_delivered",
                message_id=self.message["message_id"],
                sender_id=str(event.from_agent_id),
                receiver_id=self.node_id,
                event_id=event.event_id,
                parent_event_id=event.parent_event_id,
                platform="yulan_onesim",
                receipt_verified=True,
            )

        next_node = (
            self.route[self.route_index + 1]
            if self.route_index + 1 < len(self.route)
            else None
        )
        response = _call(
            self.runner,
            role=self.role,
            node_id=self.node_id,
            message=self.message,
            next_node=next_node,
            allowed_actions=self.allowed_actions,
        )
        self.responses.append(response)

        if self.role == "target":
            self.target_response = response
            if response.ok and response.parsed.get("accept"):
                self.trace.write(
                    "message_accepted",
                    message_id=self.message["message_id"],
                    node_id=self.node_id,
                    event_id=event.event_id,
                    platform="yulan_onesim",
                    receipt_verified=True,
                )
            return

        accepted = self.role == "source" or bool(
            response.ok and response.parsed.get("accept")
        )
        if self.role == "intermediate":
            self.trace.write(
                "message_accepted",
                message_id=self.message["message_id"],
                node_id=self.node_id,
                event_id=event.event_id,
                accepted=accepted,
                platform="yulan_onesim",
                receipt_verified=True,
            )
        forwards = bool(response.ok and response.parsed.get("forward"))
        if not (accepted and forwards and next_node is not None):
            return

        edge = (self.node_id, next_node)
        if edge == self.bridge and self.track == "remove_bridge":
            return
        if edge == self.bridge and self.track == "drop_bridge":
            self.trace.write(
                "message_dropped",
                message_id=self.message["message_id"],
                sender_id=self.node_id,
                receiver_id=next_node,
                reason="registered_bridge_drop",
                platform="yulan_onesim_adapter",
            )
            return

        child = Event(
            from_agent_id=self.node_id,
            to_agent_id=next_node,
            event_kind="RegisteredStatusUpdate",
            parent_event_id=event.event_id,
            message_id=self.message["message_id"],
            state_version=self.message["state_version"],
            payload=self.message["payload"],
        )
        self._emit(child)


async def _run_cell_async(
    task: dict[str, Any],
    variant: str,
    track: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "network_trace.jsonl"
    receipt_path = out_dir / "onesim_receipts.jsonl"
    native_flow_path = out_dir / "onesim_event_flow.json"
    for path in (trace_path, receipt_path, native_flow_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite evidence: {path}")
    trace = _Trace(trace_path)
    route = [str(node) for node in task["path"]]
    bridge = tuple(str(node) for node in task["bridge"])
    payload = payload_for(task, variant)
    message = {
        "message_id": str(task["message_id"]),
        "message_class": str(task["message_class"]),
        "state_version": str(task["state_version"]),
        "payload": payload,
    }
    allowed_actions = {
        "keep_current",
        str(task["intervention_payload"]["target_action"]),
    }
    bus = EventBus()
    roles = ["source", *(["intermediate"] * (len(route) - 2)), "target"]
    agents = [
        _T4Agent(
            node_id=node_id,
            role=roles[index],
            route_index=index,
            route=route,
            bridge=bridge,
            track=track,
            bus=bus,
            trace=trace,
            receipt_path=receipt_path,
            message=message,
            allowed_actions=allowed_actions,
            runner=model_runner,
        )
        for index, node_id in enumerate(route)
    ]
    for agent in agents:
        bus.register_agent(agent.node_id, agent)

    trace.write(
        "message_injected",
        message_id=message["message_id"],
        source_id=route[0],
        state_version=message["state_version"],
        payload=payload,
        platform="yulan_onesim_adapter",
    )
    if track == "remove_bridge":
        trace.write(
            "edge_removed",
            sender_id=bridge[0],
            receiver_id=bridge[1],
            intervention_id=f"yulan-remove-{task['id']}-bridge",
            platform="yulan_onesim_adapter",
        )

    bus_task = asyncio.create_task(bus.run())
    start = Event(
        from_agent_id="ENV",
        to_agent_id=route[0],
        event_kind="StartEvent",
        message_id=message["message_id"],
        state_version=message["state_version"],
        payload=payload,
    )
    await bus.dispatch_event(start)
    await asyncio.sleep(0)
    await bus.queue.join()

    target_agent = agents[-1]
    target_response = target_agent.target_response
    if target_response is None:
        target_response = _call(
            model_runner,
            role="target",
            node_id=route[-1],
            message=None,
            next_node=None,
            allowed_actions=allowed_actions,
        )
        target_agent.responses.append(target_response)

    target_received = bool(target_agent.received)
    action: dict[str, Any] = {}
    if target_response.ok:
        accepted = bool(target_received and target_response.parsed["accept"])
        action = {
            "action_id": f"yulan-action-{task['id']}-{variant}-{track}",
            "node_id": route[-1],
            "action": str(target_response.parsed["target_action"]),
            "evidence_message_id": message["message_id"] if accepted else None,
        }
        trace.write(
            "action_submitted",
            node_id=route[-1],
            action=action,
            platform="yulan_onesim_adapter",
        )

    await bus.dispatch_event(
        EndEvent(
            from_agent_id="benchmark_adapter",
            to_agent_id="all",
            reason="t4_cell_complete",
        )
    )
    await asyncio.wait_for(bus_task, timeout=2.0)
    native_flow = await bus.export_event_flow_data(str(native_flow_path))
    trace.write(
        "platform_termination_requested",
        platform="yulan_onesim",
        visible_in_native_flow=any(
            step.get("event_kind") == "EndEvent"
            for flow in native_flow.get("flows", [])
            for step in flow.get("steps", [])
        ),
    )

    responses = [response for agent in agents for response in agent.responses]
    receipt_rows = [
        json.loads(line)
        for line in receipt_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    path_to_target = [route[0], *[str(row["receiver_id"]) for row in receipt_rows[1:]]]
    return {
        "trace_path": str(trace_path),
        "model_trace_path": str(model_runner.path),
        "onesim_receipt_path": str(receipt_path),
        "onesim_event_flow_path": str(native_flow_path),
        "trace_nonempty": trace_path.stat().st_size > 0,
        "track": track,
        "variant": variant,
        "message_id": message["message_id"],
        "message_class": message["message_class"],
        "transport_rule": "always_forward_registered_update",
        "payload": payload,
        "target_received": target_received,
        "target_accepted": any(
            row.get("event") == "message_accepted" and row.get("node_id") == route[-1]
            for row in [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        ),
        "path_to_target": path_to_target,
        "action": action,
        "model_call_evidence_ids": [response.evidence_id for response in responses],
        "model_summary": model_runner.summary(),
        "native_event_attempts": len(bus._event_sequence),
        "verified_receipts": len(receipt_rows),
    }


def run_cell(
    task: dict[str, Any],
    variant: str,
    track: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    return asyncio.run(_run_cell_async(task, variant, track, out_dir, model_runner))


__all__ = ["run_cell"]

