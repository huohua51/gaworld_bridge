"""Execute applicable probes against YuLan-OneSim's native EventBus."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# EventBus imports pyvis only for optional visualization.  The probes exercise
# routing and JSON flow export, so keep the test environment dependency-minimal.
_pyvis = types.ModuleType("pyvis")
_pyvis.__path__ = []  # type: ignore[attr-defined]
_pyvis_network = types.ModuleType("pyvis.network")
_pyvis_network.Network = object  # type: ignore[attr-defined]
sys.modules.setdefault("pyvis", _pyvis)
sys.modules.setdefault("pyvis.network", _pyvis_network)

from onesim.events import EndEvent, Event, EventBus

from cross_platform.native_boundary_probes_v1.common import (
    PROTOCOL_VERSION,
    probe,
    write_json,
)

PLATFORM = "YuLan-OneSim"
SURFACE = "onesim.events.Event/EventBus"


@dataclass(frozen=True)
class _Profile:
    agent_type: str


class _Recorder:
    def __init__(self, node_id: str, agent_type: str):
        self.node_id = node_id
        self.profile = _Profile(agent_type)
        self.events: list[Event] = []

    def add_event(self, event: Event) -> None:
        self.events.append(event)


async def _run_async(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    flow_path = out_dir / "yulan_event_flow.json"
    bus = EventBus()
    reviewer = _Recorder("reviewer", "Reviewer")
    executor = _Recorder("executor", "Executor")
    sink = _Recorder("result-sink", "ResultSink")
    bus.register_agent(reviewer.node_id, reviewer)
    bus.register_agent(executor.node_id, executor)
    bus.register_agent(sink.node_id, sink)
    bus_task = asyncio.create_task(bus.run())

    spoof = Event(
        from_agent_id="reviewer",
        to_agent_id="executor",
        event_kind="ReviewDelivered",
        benchmark_marker="P1-SPOOF",
    )
    await bus.dispatch_event(spoof)

    unauthorized_final = Event(
        from_agent_id="reviewer",
        to_agent_id="result-sink",
        event_kind="FinalStateSubmitted",
        benchmark_marker="P3-UNAUTHORIZED-FINAL",
    )
    await bus.dispatch_event(unauthorized_final)

    trace_root = Event(
        from_agent_id="benchmark-adapter",
        to_agent_id="reviewer",
        event_kind="StartEvent",
        benchmark_marker="P4-TRACE-ROOT",
    )
    await bus.dispatch_event(trace_root)
    trace = Event(
        from_agent_id="reviewer",
        to_agent_id="executor",
        event_kind="ReviewTraceProbe",
        parent_event_id=trace_root.event_id,
        benchmark_marker="P4-TRACE",
    )
    await bus.dispatch_event(trace)
    await asyncio.sleep(0)
    await bus.queue.join()

    received_spoof = next(
        (event for event in executor.events if event.event_id == spoof.event_id), None
    )
    received_final = next(
        (
            event
            for event in sink.events
            if event.event_id == unauthorized_final.event_id
        ),
        None,
    )
    received_trace = next(
        (event for event in executor.events if event.event_id == trace.event_id), None
    )
    native_flow = await bus.export_event_flow_data(str(flow_path))

    await bus.dispatch_event(
        EndEvent(
            from_agent_id="benchmark-adapter",
            to_agent_id="all",
            reason="native_boundary_probes_complete",
        )
    )
    await asyncio.wait_for(bus_task, timeout=2.0)

    p1 = probe(
        "P1_identity_impersonation",
        surface="Event(from_agent_id)/EventBus.dispatch_event",
        capability="present",
        secure_success=received_spoof is None,
        attempted_operation=(
            "benchmark actor executor dispatches an event claiming from_agent_id=reviewer"
        ),
        evidence={
            "benchmark_actual_actor": "executor",
            "claimed_identity": "reviewer",
            "authenticated_caller_parameter_present": False,
            "event_id": spoof.event_id,
            "operation_delivered": received_spoof is not None,
        },
        limitation=(
            "This tests local Event/EventBus dispatch, not a deployment gateway or "
            "distributed transport that may add authentication."
        ),
    )
    public_methods = sorted(
        name
        for name in dir(bus)
        if not name.startswith("_") and callable(getattr(bus, name))
    )
    p2 = probe(
        "P2_private_data_read",
        surface="EventBus selected native surface",
        capability="absent",
        secure_success=None,
        attempted_operation="executor reads reviewer-owned private stored data",
        evidence={
            "selected_surface_public_methods": public_methods,
            "private_store_read_primitive_found": False,
        },
        limitation=(
            "EventBus routes events but does not expose a native owner-bound private "
            "store/read operation. An adapter-created mailbox would test the adapter, "
            "not YuLan-OneSim's EventBus."
        ),
    )
    p3 = probe(
        "P3_unauthorized_final_write",
        surface="Event/EventBus dispatch to registered result sink",
        capability="present",
        secure_success=received_final is None,
        attempted_operation=(
            "reviewer dispatches FinalStateSubmitted to the registered result sink"
        ),
        evidence={
            "claimed_role": "reviewer",
            "event_id": unauthorized_final.event_id,
            "operation_delivered": received_final is not None,
            "native_role_acl_parameter_present": False,
        },
        limitation=(
            "The sink is a passive benchmark receiver; the measured result is whether "
            "EventBus itself rejects or delivers the role-inappropriate event."
        ),
    )
    flow_text = json.dumps(native_flow, ensure_ascii=False)
    traceable = bool(
        received_trace is not None
        and received_trace.event_id == trace.event_id
        and trace.event_id in flow_text
    )
    p4 = probe(
        "P4_message_traceability",
        surface="Event.event_id plus EventBus.export_event_flow_data",
        capability="present",
        secure_success=traceable,
        attempted_operation=(
            "link one event across sender object, receiver callback, and native flow export"
        ),
        evidence={
            "sender_event_id": trace.event_id,
            "parent_event_id": trace_root.event_id,
            "receiver_event_id": (
                received_trace.event_id if received_trace is not None else ""
            ),
            "native_flow_contains_event_id": trace.event_id in flow_text,
        },
    )

    result = {
        "platform": PLATFORM,
        "protocol_version": PROTOCOL_VERSION,
        "native_surface": SURFACE,
        "new_model_calls": 0,
        "probes": [p1, p2, p3, p4],
        "native_artifacts": {"event_flow_path": str(flow_path)},
    }
    write_json(out_dir / "probe_result.json", result)
    return result


def run(out_dir: Path) -> dict[str, Any]:
    return asyncio.run(_run_async(out_dir))


__all__ = ["PLATFORM", "run"]
