"""Run one non-code T3 cell through YuLan-OneSim's native EventBus."""

from __future__ import annotations

import asyncio
import hashlib
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
sys.modules["pyvis"] = _pyvis
sys.modules["pyvis.network"] = _pyvis_network

from onesim.events import EndEvent, Event, EventBus

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from cross_platform.t3_noncode_review.protocol import (
    evidence_for,
    executor_prompt,
    executor_validator,
    proposer_prompt,
    proposer_validator,
    reviewer_prompt,
    reviewer_validator,
)


@dataclass(frozen=True)
class _Profile:
    agent_type: str


class _Trace:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.seq = 0
        self.rows: list[dict[str, Any]] = []

    def write(self, event: str, **payload: Any) -> None:
        self.seq += 1
        row = {"seq": self.seq, "event": event, **payload}
        self.rows.append(row)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class _PayloadEvent(Event):
    """YuLan event whose benchmark payload is explicitly persisted."""

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


def _payload_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _receipt(path: Path, agent_id: str, event: Event) -> None:
    payload = dict(event.get("payload") or {})
    row = {
        "event_id": event.event_id,
        "event_kind": event.event_kind,
        "parent_event_id": event.parent_event_id,
        "sender_id": str(event.from_agent_id),
        "receiver_id": agent_id,
        "payload_sha256": _payload_sha256(payload),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class _Proposer:
    def __init__(
        self,
        *,
        task: dict[str, Any],
        bus: EventBus,
        runner: RecordedModelRunner,
        trace: _Trace,
        receipts: Path,
    ) -> None:
        self.node_id = "proposer"
        self.profile = _Profile("Proposer")
        self.task = task
        self.bus = bus
        self.runner = runner
        self.trace = trace
        self.receipts = receipts
        self.response: StructuredModelResponse | None = None
        self.proposal: dict[str, Any] = {}

    def add_event(self, event: Event) -> None:
        _receipt(self.receipts, self.node_id, event)
        self.response = self.runner.call_json(
            proposer_prompt(self.task),
            task="benchmark_t3_noncode_review",
            agent_id=self.node_id,
            validator=proposer_validator,
        )
        self.proposal = dict(self.response.parsed) if self.response.ok else {}
        child = _PayloadEvent(
            from_agent_id=self.node_id,
            to_agent_id="reviewer",
            event_kind="ProposalSubmitted",
            parent_event_id=event.event_id,
            payload={"proposal": self.proposal},
        )
        self.trace.write(
            "proposal_submitted",
            event_id=child.event_id,
            proposal=self.proposal,
            sender_id=self.node_id,
            receiver_id="reviewer",
        )
        self.bus.queue.put_nowait(child)


class _Reviewer:
    def __init__(
        self,
        *,
        task: dict[str, Any],
        variant: str,
        bus: EventBus,
        runner: RecordedModelRunner,
        trace: _Trace,
        receipts: Path,
    ) -> None:
        self.node_id = "reviewer"
        self.profile = _Profile("Reviewer")
        self.task = task
        self.private_evidence = evidence_for(task, variant)
        self.bus = bus
        self.runner = runner
        self.trace = trace
        self.receipts = receipts
        self.response: StructuredModelResponse | None = None
        self.review_output: dict[str, Any] = {}
        self.delivered_review: dict[str, Any] | None = None

    def add_event(self, event: Event) -> None:
        _receipt(self.receipts, self.node_id, event)
        proposal = dict((event.get("payload") or {}).get("proposal") or {})
        self.trace.write(
            "private_evidence_read_by_reviewer",
            reader_id=self.node_id,
            evidence_ids=list(self.private_evidence["evidence_ids"]),
        )
        self.response = self.runner.call_json(
            reviewer_prompt(self.task, proposal, self.private_evidence),
            task="benchmark_t3_noncode_review",
            agent_id=self.node_id,
            validator=reviewer_validator,
        )
        self.review_output = dict(self.response.parsed) if self.response.ok else {}
        if self.response.ok:
            self.delivered_review = {
                **self.review_output,
                "review_id": f"{self.task['id']}_r1",
            }
        event_kind = "ReviewDelivered" if self.delivered_review else "ReviewUnavailable"
        child = _PayloadEvent(
            from_agent_id=self.node_id,
            to_agent_id="executor",
            event_kind=event_kind,
            parent_event_id=event.event_id,
            payload={"proposal": proposal, "review": self.delivered_review},
        )
        self.trace.write(
            "review_delivered" if self.delivered_review else "review_unavailable",
            event_id=child.event_id,
            review=self.delivered_review,
            sender_id=self.node_id,
            receiver_id="executor",
        )
        self.bus.queue.put_nowait(child)


class _Executor:
    def __init__(
        self,
        *,
        task: dict[str, Any],
        bus: EventBus,
        runner: RecordedModelRunner,
        trace: _Trace,
        receipts: Path,
    ) -> None:
        self.node_id = "executor"
        self.profile = _Profile("Executor")
        self.task = task
        self.bus = bus
        self.runner = runner
        self.trace = trace
        self.receipts = receipts
        self.response: StructuredModelResponse | None = None
        self.output: dict[str, Any] = {}
        self.delivered_review: dict[str, Any] | None = None

    def add_event(self, event: Event) -> None:
        _receipt(self.receipts, self.node_id, event)
        payload = dict(event.get("payload") or {})
        proposal = dict(payload.get("proposal") or {})
        self.delivered_review = (
            dict(payload["review"]) if isinstance(payload.get("review"), dict) else None
        )
        self.trace.write(
            "review_adopted" if self.delivered_review else "review_missing",
            review_id=(self.delivered_review or {}).get("review_id"),
            reader_id=self.node_id,
        )
        self.response = self.runner.call_json(
            executor_prompt(self.task, proposal, self.delivered_review),
            task="benchmark_t3_noncode_review",
            agent_id=self.node_id,
            validator=executor_validator,
        )
        self.output = dict(self.response.parsed) if self.response.ok else {}
        child = _PayloadEvent(
            from_agent_id=self.node_id,
            to_agent_id="result-sink",
            event_kind="FinalStateSubmitted",
            parent_event_id=event.event_id,
            payload={"executor_output": self.output},
        )
        self.trace.write(
            "final_state_submitted",
            event_id=child.event_id,
            writer_id=self.node_id,
            executor_output=self.output,
        )
        self.bus.queue.put_nowait(child)


class _ResultSink:
    def __init__(self, receipt_path: Path) -> None:
        self.node_id = "result-sink"
        self.profile = _Profile("ResultSink")
        self.receipts = receipt_path
        self.events: list[Event] = []

    def add_event(self, event: Event) -> None:
        _receipt(self.receipts, self.node_id, event)
        self.events.append(event)


async def _run_cell_async(
    task: dict[str, Any],
    variant: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "yulan_review_trace.jsonl"
    receipt_path = out_dir / "onesim_receipts.jsonl"
    native_flow_path = out_dir / "onesim_event_flow.json"
    final_path = out_dir / "final_state.json"
    for path in (trace_path, receipt_path, native_flow_path, final_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite evidence: {path}")

    bus = EventBus()
    trace = _Trace(trace_path)
    proposer = _Proposer(
        task=task, bus=bus, runner=model_runner, trace=trace, receipts=receipt_path
    )
    reviewer = _Reviewer(
        task=task,
        variant=variant,
        bus=bus,
        runner=model_runner,
        trace=trace,
        receipts=receipt_path,
    )
    executor = _Executor(
        task=task, bus=bus, runner=model_runner, trace=trace, receipts=receipt_path
    )
    sink = _ResultSink(receipt_path)
    for agent in (proposer, reviewer, executor, sink):
        bus.register_agent(agent.node_id, agent)

    bus_task = asyncio.create_task(bus.run())
    start = _PayloadEvent(
        from_agent_id="ENV",
        to_agent_id=proposer.node_id,
        event_kind="StartEvent",
        payload={"task_id": str(task["id"]), "variant": variant},
    )
    await bus.dispatch_event(start)
    await asyncio.sleep(0)
    await bus.queue.join()
    await bus.dispatch_event(
        EndEvent(
            from_agent_id="benchmark_adapter",
            to_agent_id="all",
            reason="t3_noncode_cell_complete",
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
    responses = [proposer.response, reviewer.response, executor.response]
    evidence_ids = [response.evidence_id for response in responses if response]
    return {
        "platform": "YuLan-OneSim",
        "environment_version": "yulan-onesim-eventbus-9829d722",
        "trace_version": "recipient-verified-review-and-model-jsonl-t3-noncode-v1",
        "trace_path": str(trace_path),
        "model_trace_path": str(model_runner.path),
        "onesim_receipt_path": str(receipt_path),
        "onesim_event_flow_path": str(native_flow_path),
        "final_path": str(final_path),
        "proposal": proposer.proposal,
        "review_output": reviewer.review_output,
        "delivered_review": reviewer.delivered_review,
        "executor_output": executor.output,
        "final_state": dict(executor.output.get("final_state") or {}),
        "events": [str(row["event"]) for row in trace.rows],
        "denials": [],
        "proposal_delivered": any(
            row["event_kind"] == "ProposalSubmitted"
            and row["receiver_id"] == "reviewer"
            for row in receipt_rows
        ),
        "review_delivery_verified": any(
            row["event_kind"] == "ReviewDelivered"
            and row["receiver_id"] == "executor"
            for row in receipt_rows
        ),
        "review_adoption_verified": executor.delivered_review is not None,
        "final_submission_verified": bool(sink.events),
        "private_evidence_readers": ["reviewer"],
        "state_writers": ["executor"] if sink.events else [],
        "verified_receipts": len(receipt_rows),
        "native_event_attempts": len(bus._event_sequence),
        "native_flow_count": len(native_flow.get("flows", [])),
        "model_call_evidence_ids": evidence_ids,
        "model_summary": model_runner.summary(),
    }


def run_cell(
    task: dict[str, Any],
    variant: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    return asyncio.run(_run_cell_async(task, variant, out_dir, model_runner))


__all__ = ["run_cell"]
