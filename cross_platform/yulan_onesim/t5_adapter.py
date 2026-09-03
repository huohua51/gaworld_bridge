"""T5-v3 eligibility-scope adapter backed by YuLan-OneSim's EventBus.

The benchmark owns the frozen policy semantics and state-effect oracle.  The
platform under test owns event routing and recipient delivery.  Prompts are
built only after a resident receives its YuLan event.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# EventBus imports an optional visualization stack even in headless mode.  The
# adapter does not construct WorkGraph/Network objects, so expose only the
# import symbol needed by YuLan-OneSim.
_pyvis = types.ModuleType("pyvis")
_pyvis.__path__ = []  # type: ignore[attr-defined]
_pyvis_network = types.ModuleType("pyvis.network")
_pyvis_network.Network = object  # type: ignore[attr-defined]
sys.modules["pyvis"] = _pyvis
sys.modules["pyvis.network"] = _pyvis_network

from onesim.events import EndEvent, Event, EventBus

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from exp_gm_t5_03.semantics import (
    policy_context,
    policy_signal,
    resident_directive,
)
from model_pilot.t5_v3 import _prompt, _validator


@dataclass(frozen=True)
class _Profile:
    agent_type: str


class _Trace:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.seq = 0
        self.events: list[dict[str, Any]] = []
        self.denials: list[dict[str, Any]] = []

    def write(self, event: str, **payload: Any) -> dict[str, Any]:
        self.seq += 1
        row = {"seq": self.seq, "event": event, **payload}
        self.events.append(row)
        if event == "denied":
            self.denials.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


class _PolicyNotice(Event):
    """YuLan event subclass that explicitly persists benchmark notice data."""

    def __init__(
        self,
        *,
        from_agent_id: str,
        to_agent_id: str,
        policy_id: str,
        policy_state: str,
        signal: dict[str, Any],
        eligible: bool,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            from_agent_id,
            to_agent_id,
            event_kind="PolicyNotice",
            **kwargs,
        )
        self.policy_id = policy_id
        self.policy_state = policy_state
        self.signal = dict(signal)
        self.eligible = bool(eligible)


class _DecisionTick(Event):
    """Absence-state trigger with an explicitly persisted condition label."""

    def __init__(
        self,
        *,
        from_agent_id: str,
        to_agent_id: str,
        policy_state: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            from_agent_id,
            to_agent_id,
            event_kind="DecisionTick",
            **kwargs,
        )
        self.policy_state = policy_state


def _write_receipt(path: Path, event: Event, receiver_id: str) -> None:
    row = {
        "event_id": event.event_id,
        "event_kind": event.event_kind,
        "parent_event_id": event.parent_event_id,
        "sender_id": str(event.from_agent_id),
        "receiver_id": receiver_id,
        "policy_id": event.get("policy_id"),
        "policy_state": event.get("policy_state"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class _ResidentAgent:
    def __init__(
        self,
        *,
        resident: dict[str, Any],
        task: dict[str, Any],
        policy_state: str,
        runner: RecordedModelRunner,
        trace: _Trace,
        receipt_path: Path,
    ) -> None:
        self.node_id = str(resident["agent_id"])
        self.profile = _Profile("Resident")
        self.resident = dict(resident)
        self.task = task
        self.policy_state = policy_state
        self.runner = runner
        self.trace = trace
        self.receipt_path = receipt_path
        self.state = dict(resident["state"])
        self.received: list[Event] = []
        self.response: StructuredModelResponse | None = None
        self.context: dict[str, Any] | None = None
        self.directive: dict[str, Any] | None = None
        self.submission: dict[str, Any] | None = None
        self.error: str | None = None

    def _perception(self, event: Event) -> dict[str, Any] | None:
        if event.event_kind != "PolicyNotice":
            return None
        return {
            "ok": True,
            "policy_id": str(event.policy_id),
            "signal": dict(event.signal),
            "eligible": bool(event.eligible),
        }

    def _submit_action(
        self,
        action: str,
        *,
        evidence_policy_id: str | None,
        perceived_policy: bool,
    ) -> dict[str, Any]:
        effects = {str(key): dict(value) for key, value in self.task["action_effects"].items()}
        effects.setdefault("keep_current", {})
        if action not in effects:
            row = self.trace.write(
                "denied",
                ok=False,
                reason="action_not_registered",
                agent_id=self.node_id,
                action=action,
                platform="yulan_onesim_adapter",
            )
            return dict(row)
        if action != "keep_current" and not perceived_policy:
            row = self.trace.write(
                "denied",
                ok=False,
                reason="action_evidence_not_perceived",
                agent_id=self.node_id,
                policy_id=evidence_policy_id,
                platform="yulan_onesim_adapter",
            )
            return dict(row)
        before = dict(self.state)
        after = dict(before)
        after.update(effects[action])
        changed_fields = sorted(
            field for field in after if before.get(field) != after.get(field)
        )
        record = {
            "action_id": f"yulan-policy-action-{self.node_id}-{self.trace.seq + 1}",
            "agent_id": self.node_id,
            "action": action,
            "evidence_policy_id": evidence_policy_id,
            "changed_fields": changed_fields,
        }
        self.state = after
        self.trace.write(
            "resident_action_submitted",
            agent_id=self.node_id,
            action_record=record,
            state_before=before,
            state_after=after,
            platform="yulan_onesim_adapter",
        )
        return {"ok": True, "action": record, "state": after}

    def add_event(self, event: Event) -> None:
        self.received.append(event)
        _write_receipt(self.receipt_path, event, self.node_id)
        perception = self._perception(event)
        if perception is not None:
            self.trace.write(
                "policy_perceived",
                policy_id=str(perception["policy_id"]),
                agent_id=self.node_id,
                eligible=bool(perception["eligible"]),
                event_id=event.event_id,
                receipt_verified=True,
                platform="yulan_onesim",
            )
        context = policy_context(self.task, self.policy_state, perception)
        directive = resident_directive(self.task, self.policy_state, perception)
        self.context = context
        self.directive = directive
        candidate_actions = {str(action) for action in self.task["action_effects"]}
        try:
            response = self.runner.call_json(
                _prompt(
                    resident=self.resident,
                    context=context,
                    directive=directive,
                    candidate_actions=sorted(candidate_actions),
                ),
                task="benchmark_t5_v3",
                agent_id=self.node_id,
                validator=_validator(candidate_actions),
            )
            self.response = response
            if not response.ok:
                self.submission = {
                    "agent_id": self.node_id,
                    "ok": False,
                    "reason": "model_response_invalid",
                }
                return
            adopted_policy_id = (
                str(event.policy_id)
                if perception is not None
                and context["notice_present"]
                and response.parsed["notice_seen"]
                else None
            )
            submitted = self._submit_action(
                str(response.parsed["action"]),
                evidence_policy_id=adopted_policy_id,
                perceived_policy=perception is not None,
            )
            self.submission = {"agent_id": self.node_id, **submitted}
        except Exception as exc:  # EventBus otherwise logs and swallows receiver errors.
            self.error = f"{type(exc).__name__}:{exc}"
            self.submission = {
                "agent_id": self.node_id,
                "ok": False,
                "reason": "model_call_exception",
            }
            self.trace.write(
                "denied",
                ok=False,
                reason="model_call_exception",
                agent_id=self.node_id,
                error_type=type(exc).__name__,
                platform="yulan_onesim_adapter",
            )


class _PolicyAuthority:
    def __init__(
        self,
        *,
        task: dict[str, Any],
        policy_state: str,
        bus: EventBus,
        receipt_path: Path,
    ) -> None:
        self.node_id = "policy-authority"
        self.profile = _Profile("PolicyAuthority")
        self.task = task
        self.policy_state = policy_state
        self.bus = bus
        self.receipt_path = receipt_path
        self.received: list[Event] = []
        self.emitted: list[Event] = []

    def add_event(self, event: Event) -> None:
        self.received.append(event)
        _write_receipt(self.receipt_path, event, self.node_id)
        for resident in self.task["residents"]:
            agent_id = str(resident["agent_id"])
            kwargs: dict[str, Any] = {
                "from_agent_id": self.node_id,
                "to_agent_id": agent_id,
                "parent_event_id": event.event_id,
                "policy_state": self.policy_state,
            }
            if self.policy_state == "absence":
                child = _DecisionTick(**kwargs)
            else:
                child = _PolicyNotice(
                    policy_id=str(self.task["policy_id"]),
                    signal=policy_signal(self.task, self.policy_state),
                    eligible=str(resident["group"])
                    in {str(group) for group in self.task["target_groups"]},
                    **kwargs,
                )
            self.emitted.append(child)
            self.bus.queue.put_nowait(child)


async def _run_cell_async(
    task: dict[str, Any],
    policy_state: str,
    track: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    if track != "full":
        raise ValueError("YuLan T5-v3 pilot is registered for full track only")
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "policy_trace.jsonl"
    receipt_path = out_dir / "onesim_receipts.jsonl"
    native_flow_path = out_dir / "onesim_event_flow.json"
    for path in (trace_path, receipt_path, native_flow_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite evidence: {path}")

    trace = _Trace(trace_path)
    trace.write(
        "population_registered",
        residents=[dict(resident) for resident in task["residents"]],
        platform="benchmark_policy_oracle",
    )
    policy_id: str | None = None
    registration: dict[str, Any] | None = None
    if policy_state != "absence":
        policy_id = str(task["policy_id"])
        registered_policy = {
            "policy_id": policy_id,
            "policy_version": str(task["policy_version"]),
            "effective_step": int(task["effective_step"]),
            "condition": (
                "real_policy" if policy_state == "binding" else "placebo_policy"
            ),
            "target_groups": [str(group) for group in task["target_groups"]],
            "signal": policy_signal(task, policy_state),
        }
        trace.write(
            "policy_registered",
            policy=registered_policy,
            platform="benchmark_policy_oracle",
        )
        registration = {"ok": True, "policy": registered_policy}
    step = int(task["effective_step"])
    trace.write("clock_advanced", step=step, platform="benchmark_policy_oracle")
    if policy_id:
        trace.write(
            "policy_activated",
            policy_id=policy_id,
            policy_version=str(task["policy_version"]),
            step=step,
            platform="benchmark_policy_oracle",
        )

    bus = EventBus()
    authority = _PolicyAuthority(
        task=task,
        policy_state=policy_state,
        bus=bus,
        receipt_path=receipt_path,
    )
    residents = [
        _ResidentAgent(
            resident=dict(resident),
            task=task,
            policy_state=policy_state,
            runner=model_runner,
            trace=trace,
            receipt_path=receipt_path,
        )
        for resident in task["residents"]
    ]
    bus.register_agent(authority.node_id, authority)
    for resident in residents:
        bus.register_agent(resident.node_id, resident)

    bus_task = asyncio.create_task(bus.run())
    start = Event(
        from_agent_id="ENV",
        to_agent_id=authority.node_id,
        event_kind="StartEvent",
        policy_state=policy_state,
        task_id=str(task["id"]),
    )
    await bus.dispatch_event(start)
    await asyncio.sleep(0)
    await bus.queue.join()
    await bus.dispatch_event(
        EndEvent(
            from_agent_id="benchmark_adapter",
            to_agent_id="all",
            reason="t5_cell_complete",
        )
    )
    await asyncio.wait_for(bus_task, timeout=2.0)
    native_flow = await bus.export_event_flow_data(str(native_flow_path))

    receipt_rows = [
        json.loads(line)
        for line in receipt_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    policy_receipts = [
        row for row in receipt_rows if row["event_kind"] == "PolicyNotice"
    ]
    decision_receipts = [
        row for row in receipt_rows if row["event_kind"] == "DecisionTick"
    ]
    responses = [resident.response for resident in residents if resident.response]
    return {
        "trace_path": str(trace_path),
        "model_trace_path": str(model_runner.path),
        "onesim_receipt_path": str(receipt_path),
        "onesim_event_flow_path": str(native_flow_path),
        "trace_nonempty": trace_path.stat().st_size > 0,
        "policy_state": policy_state,
        "track": track,
        "policy_id": policy_id,
        "registration": registration,
        "advanced": {"ok": True, "step": step, "activated": [policy_id] if policy_id else []},
        "policy_active": bool(policy_id),
        "perceptions": [
            {
                "agent_id": resident.node_id,
                "ok": True,
                "policy_id": policy_id,
                "eligible": bool(resident.directive and resident.directive["target_match"]),
            }
            for resident in residents
            if policy_id
        ],
        "policy_contexts": [
            {"agent_id": resident.node_id, **dict(resident.context or {})}
            for resident in residents
        ],
        "resident_directives": [
            {"agent_id": resident.node_id, **dict(resident.directive or {})}
            for resident in residents
        ],
        "submissions": [dict(resident.submission or {}) for resident in residents],
        "events": [str(row["event"]) for row in trace.events],
        "denials": list(trace.denials),
        "model_call_evidence_ids": [response.evidence_id for response in responses],
        "model_summary": model_runner.summary(),
        "native_event_attempts": len(bus._event_sequence),
        "verified_receipts": len(receipt_rows),
        "verified_policy_receipts": len(policy_receipts),
        "verified_decision_receipts": len(decision_receipts),
        "resident_errors": {
            resident.node_id: resident.error for resident in residents if resident.error
        },
        "native_flow_count": len(native_flow.get("flows", [])),
    }


def run_cell(
    task: dict[str, Any],
    policy_state: str,
    track: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    return asyncio.run(
        _run_cell_async(task, policy_state, track, out_dir, model_runner)
    )


__all__ = ["run_cell"]
