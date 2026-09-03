"""Replay one already-sampled review through YuLan-OneSim's EventBus."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_pyvis = types.ModuleType("pyvis")
_pyvis.__path__ = []  # type: ignore[attr-defined]
_pyvis_network = types.ModuleType("pyvis.network")
_pyvis_network.Network = object  # type: ignore[attr-defined]
sys.modules.setdefault("pyvis", _pyvis)
sys.modules.setdefault("pyvis.network", _pyvis_network)

from onesim.events import EndEvent, Event, EventBus

from cross_platform.t3_noncode_replay_v2.protocol import (
    expected_executor,
    payload_sha256,
    registered_proposal,
)


@dataclass(frozen=True)
class _Profile:
    agent_type: str


class _PayloadEvent(Event):
    def __init__(
        self,
        *,
        from_agent_id: str,
        to_agent_id: str,
        event_kind: str,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(
            from_agent_id,
            to_agent_id,
            event_kind=event_kind,
            **kwargs,
        )
        self.payload = dict(payload)


def _append(path: Path, event: str, **payload: Any) -> None:
    row = {"event": event, **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _receipt(path: Path, agent_id: str, event: Event) -> None:
    payload = dict(event.get("payload") or {})
    _append(
        path,
        "received",
        event_id=event.event_id,
        event_kind=event.event_kind,
        parent_event_id=event.parent_event_id,
        sender_id=str(event.from_agent_id),
        receiver_id=agent_id,
        payload_sha256=payload_sha256(payload),
    )


class _Executor:
    def __init__(
        self, task: dict[str, Any], bus: EventBus, trace: Path, receipts: Path
    ):
        self.node_id = "executor"
        self.profile = _Profile("Executor")
        self.task = task
        self.bus = bus
        self.trace = trace
        self.receipts = receipts
        self.delivered_review: dict[str, Any] | None = None
        self.output: dict[str, Any] = {}

    def add_event(self, event: Event) -> None:
        _receipt(self.receipts, self.node_id, event)
        payload = dict(event.get("payload") or {})
        self.delivered_review = (
            dict(payload["review"]) if isinstance(payload.get("review"), dict) else None
        )
        _append(
            self.trace,
            "review_received" if self.delivered_review else "review_unavailable",
            event_id=event.event_id,
            ingress_review_sha256=payload_sha256(self.delivered_review),
        )
        self.output = expected_executor(self.task, self.delivered_review)
        child = _PayloadEvent(
            from_agent_id=self.node_id,
            to_agent_id="result-sink",
            event_kind="FinalStateSubmitted",
            parent_event_id=event.event_id,
            payload={"executor_output": self.output},
        )
        self.bus.queue.put_nowait(child)


class _ResultSink:
    def __init__(self, receipts: Path):
        self.node_id = "result-sink"
        self.profile = _Profile("ResultSink")
        self.receipts = receipts
        self.events: list[Event] = []

    def add_event(self, event: Event) -> None:
        _receipt(self.receipts, self.node_id, event)
        self.events.append(event)


async def _replay_async(
    task: dict[str, Any],
    variant: str,
    review: dict[str, Any] | None,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    trace_path = out_dir / "yulan_replay_trace.jsonl"
    receipt_path = out_dir / "onesim_receipts.jsonl"
    native_flow_path = out_dir / "onesim_event_flow.json"
    final_path = out_dir / "final_state.json"
    manifest_path = out_dir / "replay_manifest.json"

    bus = EventBus()
    executor = _Executor(task, bus, trace_path, receipt_path)
    sink = _ResultSink(receipt_path)
    bus.register_agent(executor.node_id, executor)
    bus.register_agent(sink.node_id, sink)
    bus_task = asyncio.create_task(bus.run())
    start = _PayloadEvent(
        from_agent_id="reviewer",
        to_agent_id=executor.node_id,
        event_kind="ReviewDelivered" if review is not None else "ReviewUnavailable",
        payload={
            "task_id": str(task["id"]),
            "variant": variant,
            "proposal": registered_proposal(task),
            "review": review,
        },
    )
    await bus.dispatch_event(start)
    await asyncio.sleep(0)
    await bus.queue.join()
    await bus.dispatch_event(
        EndEvent(
            from_agent_id="benchmark_adapter",
            to_agent_id="all",
            reason="shared_review_replay_complete",
        )
    )
    await asyncio.wait_for(bus_task, timeout=2.0)
    native_flow = await bus.export_event_flow_data(str(native_flow_path))
    final_path.write_text(
        json.dumps(executor.output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    receipt_rows = [
        json.loads(line)
        for line in receipt_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result = {
        "platform": "YuLan-OneSim",
        "environment_version": "yulan-onesim-eventbus-9829d722",
        "trace_version": "shared-review-replay-v2",
        "trace_path": str(trace_path),
        "onesim_receipt_path": str(receipt_path),
        "onesim_event_flow_path": str(native_flow_path),
        "final_path": str(final_path),
        "ingress_review": review,
        "ingress_review_sha256": payload_sha256(review),
        "delivered_review": executor.delivered_review,
        "delivered_review_sha256": payload_sha256(executor.delivered_review),
        "executor_output": executor.output,
        "proposal_delivered": True,
        "review_delivery_verified": any(
            row.get("event_kind") == "ReviewDelivered"
            and row.get("receiver_id") == "executor"
            for row in receipt_rows
        ),
        "review_adoption_verified": executor.delivered_review is not None,
        "final_submission_verified": bool(sink.events),
        "payload_exact": executor.delivered_review == review,
        "private_evidence_readers": ["reviewer"],
        "state_writers": ["executor"] if sink.events else [],
        "verified_receipts": len(receipt_rows),
        "native_event_attempts": len(bus._event_sequence),
        "native_flow_count": len(native_flow.get("flows", [])),
        "events": [
            str(row.get("event") or "")
            for row in [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        ],
        "denials": [],
    }
    manifest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def replay(
    task: dict[str, Any],
    variant: str,
    review: dict[str, Any] | None,
    out_dir: Path,
) -> dict[str, Any]:
    return asyncio.run(_replay_async(task, variant, review, out_dir))


__all__ = ["replay"]
