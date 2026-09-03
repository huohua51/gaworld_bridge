"""Deterministic calibration of GAWorld T4 evidence on YuLan-OneSim.

This runner deliberately uses YuLan-OneSim's real EventBus but rule-based probe
agents.  It therefore spends no model/API tokens and isolates event transport
and observability from LLM behaviour.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# EventBus imports WorkGraph, which imports pyvis at module import time even when
# visualization is unused.  R0 is headless, so provide only the optional symbol
# WorkGraph needs instead of installing IPython/Jupyter into the minimal venv.
_pyvis = types.ModuleType("pyvis")
_pyvis.__path__ = []  # type: ignore[attr-defined]
_pyvis_network = types.ModuleType("pyvis.network")
_pyvis_network.Network = object  # type: ignore[attr-defined]
sys.modules["pyvis"] = _pyvis
sys.modules["pyvis.network"] = _pyvis_network

from onesim.events import EndEvent, Event, EventBus


@dataclass(frozen=True)
class _Profile:
    agent_type: str


class _ProbeAgent:
    """Minimal EventBus receiver with an optional deterministic next hop."""

    def __init__(
        self,
        *,
        agent_id: str,
        agent_type: str,
        bus: EventBus,
        input_kind: str,
        next_agent_id: str | None = None,
        next_kind: str | None = None,
        forward: bool = True,
    ) -> None:
        self.agent_id = agent_id
        self.profile = _Profile(agent_type)
        self.bus = bus
        self.input_kind = input_kind
        self.next_agent_id = next_agent_id
        self.next_kind = next_kind
        self.forward = forward
        self.received: list[Event] = []
        self.emitted: list[Event] = []

    def add_event(self, event: Event) -> None:
        self.received.append(event)
        if (
            self.forward
            and event.event_kind == self.input_kind
            and self.next_agent_id is not None
            and self.next_kind is not None
        ):
            child = Event(
                from_agent_id=self.agent_id,
                to_agent_id=self.next_agent_id,
                event_kind=self.next_kind,
                parent_event_id=event.event_id,
                timestamp=event.timestamp + 1.0,
                message_id=event.get("message_id", "registered-update-r0"),
            )
            self.emitted.append(child)
            self.bus.queue.put_nowait(child)


def _event_record(record: tuple[Any, ...]) -> dict[str, Any]:
    timestamp, kind, sender, receiver, event_id, sender_type, receiver_type = record
    return {
        "timestamp": timestamp,
        "event_kind": kind,
        "from_agent_id": sender,
        "to_agent_id": receiver,
        "event_id": event_id,
        "from_agent_type": sender_type,
        "to_agent_type": receiver_type,
    }


async def _finish(bus: EventBus, task: asyncio.Task[None]) -> None:
    await bus.queue.join()
    await bus.dispatch_event(
        EndEvent(
            from_agent_id="benchmark_adapter",
            to_agent_id="all",
            reason="r0_case_complete",
            timestamp=99.0,
        )
    )
    await asyncio.wait_for(task, timeout=2.0)


async def _run_path_case(*, bridge_forwards: bool) -> dict[str, Any]:
    bus = EventBus()
    source = _ProbeAgent(
        agent_id="sensor",
        agent_type="Source",
        bus=bus,
        input_kind="StartEvent",
        next_agent_id="bridge",
        next_kind="RegisteredUpdate",
    )
    bridge = _ProbeAgent(
        agent_id="bridge",
        agent_type="Bridge",
        bus=bus,
        input_kind="RegisteredUpdate",
        next_agent_id="target",
        next_kind="TargetAction",
        forward=bridge_forwards,
    )
    target = _ProbeAgent(
        agent_id="target",
        agent_type="Target",
        bus=bus,
        input_kind="TargetAction",
    )
    for agent in (source, bridge, target):
        bus.register_agent(agent.agent_id, agent)

    run_task = asyncio.create_task(bus.run())
    start = Event(
        from_agent_id="ENV",
        to_agent_id="sensor",
        event_kind="StartEvent",
        event_id="r0-start",
        timestamp=1.0,
        message_id="registered-update-r0",
    )
    await bus.dispatch_event(start)
    await asyncio.sleep(0)
    await _finish(bus, run_task)
    exported = await bus.export_event_flow_data()

    raw_events = [start, *source.emitted, *bridge.emitted]
    raw_parent_by_id = {
        event.event_id: event.parent_event_id
        for event in raw_events
        if event.parent_event_id is not None
    }
    exported_steps = [
        step for flow in exported["flows"] for step in flow.get("steps", [])
    ]
    exported_parent_by_id = {
        step["event_id"]: step.get("parent_event_id") for step in exported_steps
    }
    receipt_sequence = [
        {"agent_id": agent.agent_id, "event_id": event.event_id, "event_kind": event.event_kind}
        for agent in (source, bridge, target)
        for event in agent.received
    ]
    expected_receivers = ["sensor", "bridge", "target"]
    actual_receivers = [item["agent_id"] for item in receipt_sequence]

    return {
        "case": "full_registered_path" if bridge_forwards else "adapter_drop_at_bridge",
        "event_bus_attempt_sequence": [_event_record(row) for row in bus._event_sequence],
        "recipient_receipt_sequence": receipt_sequence,
        "recipient_verified_complete_path": actual_receivers == expected_receivers,
        "recipient_verified_target_receipt": bool(target.received),
        "raw_parent_by_event_id": raw_parent_by_id,
        "exported_parent_by_event_id": exported_parent_by_id,
        "exported_exact_parent_lineage": all(
            exported_parent_by_id.get(event_id) == parent_id
            for event_id, parent_id in raw_parent_by_id.items()
        ),
        "exported_global_termination_detectability": any(
            row["event_kind"] == "EndEvent"
            for row in [_event_record(item) for item in bus._event_sequence]
        ),
        "exported_flow_data": exported,
    }


async def _run_unknown_target_case() -> dict[str, Any]:
    bus = EventBus()
    run_task = asyncio.create_task(bus.run())
    unknown = Event(
        from_agent_id="sensor",
        to_agent_id="missing_target",
        event_kind="RegisteredUpdate",
        event_id="r0-unknown-target",
        timestamp=1.0,
        message_id="registered-update-r0",
    )
    await bus.dispatch_event(unknown)
    await asyncio.sleep(0)
    await _finish(bus, run_task)
    exported = await bus.export_event_flow_data()
    exported_event_ids = {
        step["event_id"]
        for flow in exported["flows"]
        for step in flow.get("steps", [])
    }
    attempted_event_ids = {row[4] for row in bus._event_sequence}
    return {
        "case": "unknown_target",
        "event_bus_attempt_sequence": [_event_record(row) for row in bus._event_sequence],
        "recipient_receipt_sequence": [],
        "recipient_verified_target_receipt": False,
        "attempt_present_in_internal_sequence": unknown.event_id in attempted_event_ids,
        "exported_unknown_target_detectability": unknown.event_id in exported_event_ids,
        "omitted_single_event_flows": unknown.event_id not in exported_event_ids,
        "exported_global_termination_detectability": any(
            row[1] == "EndEvent" for row in bus._event_sequence
        ),
        "exported_flow_data": exported,
    }


async def _run_all() -> dict[str, Any]:
    full, dropped, unknown = await _run_path_case(bridge_forwards=True), await _run_path_case(
        bridge_forwards=False
    ), await _run_unknown_target_case()
    checks = {
        "positive_control_complete_path": full["recipient_verified_complete_path"],
        "negative_control_bridge_drop_blocks_target": not dropped[
            "recipient_verified_target_receipt"
        ],
        "negative_control_unknown_target_not_delivered": not unknown[
            "recipient_verified_target_receipt"
        ],
        "export_preserves_exact_multihop_lineage": full[
            "exported_exact_parent_lineage"
        ],
        "export_exposes_unknown_target_attempt": unknown[
            "exported_unknown_target_detectability"
        ],
        "export_exposes_global_termination": full[
            "exported_global_termination_detectability"
        ],
    }
    return {
        "schema_version": "yulan-onesim-r0-v1",
        "model_calls": 0,
        "cases": [full, dropped, unknown],
        "checks": checks,
        "calibration_pass": all(
            checks[name]
            for name in (
                "positive_control_complete_path",
                "negative_control_bridge_drop_blocks_target",
                "negative_control_unknown_target_not_delivered",
            )
        ),
        "native_export_sufficient_for_gaworld_scoring": all(
            checks[name]
            for name in (
                "export_preserves_exact_multihop_lineage",
                "export_exposes_unknown_target_attempt",
                "export_exposes_global_termination",
            )
        ),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    result = asyncio.run(_run_all())
    registration = Path(__file__).with_name("registration_r0.yaml")
    result["evidence"] = {
        "registration": str(registration),
        "registration_sha256": _sha256(registration),
        "runner_sha256": _sha256(Path(__file__)),
    }
    result_path = args.out / "result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"result": str(result_path), **result["checks"]}, indent=2))
    return 0 if result["calibration_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
