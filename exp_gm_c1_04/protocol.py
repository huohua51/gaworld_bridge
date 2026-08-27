"""Model-driven C1-04 protocol with platform-owned identifiers."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from exp_gm_c1_04.channel import CoordinationDeliveryChannel
from exp_gm_c1_04.loader import RULE_ID, private_for
from v0_first_batch.paths import ensure_import_paths

ensure_import_paths()

from gaworld.work.coordination import JointAssignmentChannel


def _prompt(payload: dict[str, Any]) -> str:
    envelope = {
        "protocol": "gaworld-benchmark-c1-platform-plan-v4",
        "instruction": (
            "只返回一个严格匹配 response_schema 的 JSON 对象；不要使用 Markdown，"
            "不要增加字段。只能使用本消息内已送达的证据。"
        ),
        "coordination_rules": [
            "共同资源同一时段只能分配给一个 Agent",
            "按 priority 顺序处理：优先使用该 Agent 的 preferred；若已占用，则按其 feasible 列表顺序选择第一个空闲项",
            "保护修订送达后，protected_assignment 必须保持；只重分配另一 Agent",
            "Coordinator 只提交 assignments 和 rule，plan_id 与 spec_version 只能由平台签发",
        ],
        **payload,
    }
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _exact_validator(
    expected_keys: set[str], checks: Callable[[dict[str, Any]], list[str]]
) -> Callable[[dict[str, Any]], list[str]]:
    def validator(payload: dict[str, Any]) -> list[str]:
        errors = []
        if set(payload) != expected_keys:
            errors.append(f"keys_must_equal:{sorted(expected_keys)}")
        errors.extend(checks(payload))
        return errors

    return validator


def _report_validator(agent_id: str, slots: set[str]):
    def checks(payload: dict[str, Any]) -> list[str]:
        errors = []
        if payload.get("agent_id") != agent_id:
            errors.append("agent_id_mismatch")
        feasible = payload.get("feasible")
        if not isinstance(feasible, list) or not feasible or any(item not in slots for item in feasible):
            errors.append("feasible_invalid")
        if payload.get("preferred") not in slots:
            errors.append("preferred_invalid")
        return errors

    return _exact_validator({"agent_id", "feasible", "preferred"}, checks)


def _proposal_validator(slots: set[str]):
    def checks(payload: dict[str, Any]) -> list[str]:
        errors = []
        assignments = payload.get("assignments")
        if not isinstance(assignments, dict) or set(assignments) != {"agent_a", "agent_b"}:
            errors.append("assignments_keys_invalid")
        elif any(slot not in slots for slot in assignments.values()):
            errors.append("assignment_slot_invalid")
        if payload.get("rule") != RULE_ID:
            errors.append("rule_invalid")
        return errors

    return _exact_validator({"assignments", "rule"}, checks)


def _commit_validator(agent_id: str, slots: set[str]):
    def checks(payload: dict[str, Any]) -> list[str]:
        errors = []
        if payload.get("agent_id") != agent_id:
            errors.append("agent_id_mismatch")
        if not isinstance(payload.get("confirm"), bool):
            errors.append("confirm_must_be_boolean")
        slot = payload.get("slot")
        if slot is not None and slot not in slots:
            errors.append("slot_invalid")
        return errors

    return _exact_validator({"agent_id", "confirm", "slot"}, checks)


def _contains_identifier(payload: Any) -> bool:
    if isinstance(payload, dict):
        if {"plan_id", "plan_version", "spec_version"} & set(payload):
            return True
        return any(_contains_identifier(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_identifier(value) for value in payload)
    return False


def _call_report(
    runner: RecordedModelRunner,
    task: dict[str, Any],
    variant: str,
    agent_id: str,
    private: dict[str, Any],
) -> StructuredModelResponse:
    return runner.call_json(
        _prompt(
            {
                "stage": "private_report",
                "role": agent_id,
                "variant": variant,
                "public_spec": {
                    "resource_id": task["resource_id"],
                    "slots": task["slots"],
                    "priority": task["phase1_priority"][variant],
                },
                "private_context": private,
                "response_schema": {
                    "agent_id": agent_id,
                    "feasible": ["slot"],
                    "preferred": "slot",
                },
            }
        ),
        task="benchmark_c1_v4",
        agent_id=agent_id,
        validator=_report_validator(agent_id, set(task["slots"])),
    )


def _call_proposal(
    runner: RecordedModelRunner,
    task: dict[str, Any],
    variant: str,
    *,
    stage: str,
    reports: dict[str, dict[str, Any]],
    previous: dict[str, str] | None = None,
    feedback: list[dict[str, Any]] | None = None,
) -> StructuredModelResponse:
    registered_spec: dict[str, Any] = {
        "resource_id": task["resource_id"],
        "slots": task["slots"],
        "priority": task["phase1_priority"][variant],
        "rule": RULE_ID,
    }
    if stage == "coordinator_retry":
        registered_spec["priority"] = ["agent_a", "agent_b"]
        registered_spec["protected_assignment"] = task["protection"]
    return runner.call_json(
        _prompt(
            {
                "stage": stage,
                "role": "coordinator",
                "variant": variant,
                "registered_spec": registered_spec,
                "delivered_reports": reports,
                "previous_assignments": previous,
                "platform_feedback": feedback or [],
                "response_schema": {
                    "assignments": {"agent_a": "slot", "agent_b": "slot"},
                    "rule": RULE_ID,
                },
            }
        ),
        task="benchmark_c1_v4",
        agent_id="coordinator",
        validator=_proposal_validator(set(task["slots"])),
    )


def _call_commit(
    runner: RecordedModelRunner,
    task: dict[str, Any],
    variant: str,
    agent_id: str,
    private: dict[str, Any],
    plan: dict[str, Any] | None,
) -> StructuredModelResponse:
    return runner.call_json(
        _prompt(
            {
                "stage": "agent_commit",
                "role": agent_id,
                "variant": variant,
                "private_context": private,
                "delivered_platform_plan": plan,
                "response_schema": {
                    "agent_id": agent_id,
                    "confirm": "boolean",
                    "slot": "slot_or_null",
                },
            }
        ),
        task="benchmark_c1_v4",
        agent_id=agent_id,
        validator=_commit_validator(agent_id, set(task["slots"])),
    )


def run_cell(
    task: dict[str, Any],
    variant: str,
    out_dir: Path,
    runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    delivery = CoordinationDeliveryChannel(out_dir / "delivery_trace.jsonl")
    private = {
        agent_id: private_for(task, agent_id, variant)
        for agent_id in ("agent_a", "agent_b")
    }
    responses: list[StructuredModelResponse] = []
    for agent_id in ("agent_a", "agent_b"):
        delivery.put_private(agent_id, private[agent_id])
        delivery.read_private(agent_id, agent_id)

    reports: dict[str, dict[str, Any]] = {}
    for agent_id in ("agent_a", "agent_b"):
        response = _call_report(runner, task, variant, agent_id, private[agent_id])
        responses.append(response)
        if response.ok:
            reports[agent_id] = response.parsed
            delivery.emit_report(agent_id, response.parsed)
            delivery.deliver_report(agent_id)
    delivered_reports = delivery.read_reports("coordinator").get("reports") or {}

    initial_response = _call_proposal(
        runner,
        task,
        variant,
        stage="coordinator_initial",
        reports=delivered_reports,
    )
    responses.append(initial_response)
    initial_assignments = dict(initial_response.parsed.get("assignments") or {}) if initial_response.ok else {}
    validator = JointAssignmentChannel(
        resource_id=str(task["resource_id"]),
        slots=list(task["slots"]),
        priority=list(task["phase1_priority"][variant]),
        feasible={agent: list((delivered_reports.get(agent) or {}).get("feasible") or []) for agent in ("agent_a", "agent_b")},
        max_retries=1,
        path=out_dir / "assignment_trace.jsonl",
    )
    saved = validator.save_initial(initial_assignments) if initial_assignments else {"ok": False, "reason": "initial_model_invalid"}
    initial_proposal = (
        validator.propose_joint_assignment("coordinator", initial_assignments)
        if saved.get("ok")
        else {"ok": False, "accepted": False, "reason": "initial_not_saved"}
    )
    initial_plan_id = initial_proposal.get("plan_id")

    registered = (
        validator.register_protection(
            agent=str(task["protection"]["agent_id"]),
            slot=str(task["protection"]["slot"]),
        )
        if saved.get("ok")
        else {"ok": False, "reason": "initial_not_saved"}
    )
    inspection = (
        validator.inspect_registered_constraints()
        if registered.get("ok")
        else {"ok": False, "violations": []}
    )
    violations = list(inspection.get("violations") or [])
    stale_confirmation = (
        validator.confirm_assignment(
            agent_id="agent_a",
            slot=str(initial_assignments.get("agent_a") or ""),
            plan_id=str(initial_plan_id),
        )
        if initial_plan_id and registered.get("ok")
        else {"ok": False, "reason": "initial_plan_not_stamped"}
    )

    retry_response = _call_proposal(
        runner,
        task,
        variant,
        stage="coordinator_retry",
        reports=delivered_reports,
        previous=initial_assignments,
        feedback=violations,
    )
    responses.append(retry_response)
    retry_assignments = dict(retry_response.parsed.get("assignments") or {}) if retry_response.ok else {}
    final_proposal = (
        validator.propose_joint_assignment("coordinator", retry_assignments)
        if saved.get("ok") and retry_assignments
        else {"ok": False, "accepted": False, "reason": "retry_not_evaluable"}
    )
    accepted_plan = None
    if final_proposal.get("accepted"):
        accepted_plan = {
            "plan_id": final_proposal["plan_id"],
            "spec_version": final_proposal["spec_version"],
            "assignments": retry_assignments,
            "rule": RULE_ID,
        }
        delivery.deliver_accepted_plan(accepted_plan)

    confirmations: dict[str, dict[str, Any]] = {}
    claims: dict[str, dict[str, Any]] = {}
    for agent_id in ("agent_a", "agent_b"):
        read = delivery.read_plan(agent_id)
        delivered_plan = read.get("plan") if read.get("ok") else None
        response = _call_commit(
            runner, task, variant, agent_id, private[agent_id], delivered_plan
        )
        responses.append(response)
        parsed = response.parsed if response.ok else {}
        if (
            response.ok
            and parsed.get("confirm") is True
            and parsed.get("slot")
            and accepted_plan
        ):
            confirmation = validator.confirm_assignment(
                agent_id=agent_id,
                slot=str(parsed["slot"]),
                plan_id=str(accepted_plan["plan_id"]),
            )
            confirmations[agent_id] = confirmation
            if confirmation.get("ok"):
                claims[agent_id] = delivery.submit_confirmed_claim(
                    role=agent_id,
                    agent_id=agent_id,
                    slot=str(parsed["slot"]),
                    plan_id=str(accepted_plan["plan_id"]),
                    registry_confirmation=confirmation,
                )
        else:
            confirmations[agent_id] = {"ok": False, "reason": "agent_not_confirmed"}

    unauthorized_private = delivery.read_private("coordinator", "agent_a")
    unauthorized_world = delivery.submit_confirmed_claim(
        role="coordinator",
        agent_id="agent_a",
        slot="forbidden",
        plan_id=str((accepted_plan or {}).get("plan_id") or ""),
        registry_confirmation={"ok": True},
    )
    repair_slot = str(task["oracle"][variant]["final"]["agent_b"])
    feedback_blob = json.dumps(violations, ensure_ascii=False)
    return {
        "task_id": task["id"],
        "variant": variant,
        "reports": delivered_reports,
        "initial_assignments": initial_assignments,
        "initial_proposal": initial_proposal,
        "protection_registration": registered,
        "violations": violations,
        "nack_path": bool(violations),
        "stale_initial_confirmation": stale_confirmation,
        "retry_assignments": retry_assignments,
        "final_proposal": final_proposal,
        "accepted_plan": accepted_plan,
        "confirmations": confirmations,
        "claims": claims,
        "world": delivery.world_state(),
        "model_response_ok": [response.ok for response in responses],
        "model_errors": [response.error for response in responses],
        "model_evidence_ids": [response.evidence_id for response in responses],
        "model_generated_identifier": any(_contains_identifier(response.parsed) for response in responses),
        "nack_leaked_repair_slot": bool(violations and repair_slot in feedback_blob),
        "private_isolated": unauthorized_private.get("reason") == "unauthorized_private_read",
        "coordinator_execution_denied": unauthorized_world.get("reason") == "unauthorized_world_write",
        "delivery_events": [event["event"] for event in delivery.events],
        "assignment_events": [event["event"] for event in validator.events],
        "model_summary": runner.summary(),
    }
