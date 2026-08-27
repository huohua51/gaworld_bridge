"""C1-05 loop with an explicit authoritative-current-spec transition."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from exp_gm_c1_04.channel import CoordinationDeliveryChannel
from exp_gm_c1_05.loader import RULE_ID, private_for
from v0_first_batch.paths import ensure_import_paths

ensure_import_paths()
from gaworld.work.coordination import JointAssignmentChannel


def _prompt(payload: dict[str, Any]) -> str:
    stage = payload["stage"]
    rules = [
        "一个资源时段最多分配给一个 Agent。",
        "模型只能输出 assignments/rule 或 agent confirmation；plan_id 与 spec_version 由平台签发。",
    ]
    if stage == "coordinator_initial":
        rules.extend(
            [
                "此阶段只使用 phase1_spec。按 priority 顺序分配。",
                "对每个 Agent：preferred 可行且未占用时选 preferred，否则按 feasible 的书写顺序选第一个空闲项。",
            ]
        )
    elif stage == "coordinator_retry":
        rules.extend(
            [
                "phase1_spec 和 previous_assignments 已失效，只是历史证据；不得把旧分配当成当前约束。",
                "authoritative_current_spec 是唯一有效规范。",
                "步骤1：把 protected_assignment.agent_id 的分配精确设为 protected_assignment.slot，即使它不同于旧分配或旧 preferred。",
                "步骤2：把该保护时段标记为已占用。",
                "步骤3：对另一 Agent，从 delivered_reports 中该 Agent 的 feasible 列表首项开始扫描，选择第一个未占用项。",
                "不得保留与 protected_assignment.slot 不同的旧 protected-agent 分配；不得输出两个相同时段。",
            ]
        )
    return json.dumps(
        {
            "protocol": "gaworld-benchmark-c1-authoritative-current-spec-v5",
            "instruction": "只返回严格匹配 response_schema 的一个 JSON 对象；不要使用 Markdown，不要增加字段。",
            "registered_rules": rules,
            **payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_report(agent_id: str, slots: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        errors = []
        if set(payload) != {"agent_id", "feasible", "preferred"}:
            errors.append("report_keys_invalid")
        if payload.get("agent_id") != agent_id:
            errors.append("agent_id_mismatch")
        feasible = payload.get("feasible")
        if not isinstance(feasible, list) or not feasible or any(item not in slots for item in feasible):
            errors.append("feasible_invalid")
        if payload.get("preferred") not in slots:
            errors.append("preferred_invalid")
        return errors

    return validator


def _validate_proposal(slots: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        errors = []
        if set(payload) != {"assignments", "rule"}:
            errors.append("proposal_keys_invalid")
        assignments = payload.get("assignments")
        if not isinstance(assignments, dict) or set(assignments) != {"agent_a", "agent_b"}:
            errors.append("assignments_invalid")
        elif any(slot not in slots for slot in assignments.values()):
            errors.append("assignment_slot_invalid")
        if payload.get("rule") != RULE_ID:
            errors.append("rule_invalid")
        return errors

    return validator


def _validate_commit(agent_id: str, slots: set[str]):
    def validator(payload: dict[str, Any]) -> list[str]:
        errors = []
        if set(payload) != {"agent_id", "confirm", "slot"}:
            errors.append("commit_keys_invalid")
        if payload.get("agent_id") != agent_id:
            errors.append("agent_id_mismatch")
        if not isinstance(payload.get("confirm"), bool):
            errors.append("confirm_invalid")
        if payload.get("slot") is not None and payload.get("slot") not in slots:
            errors.append("slot_invalid")
        return errors

    return validator


def _call(
    runner: RecordedModelRunner,
    payload: dict[str, Any],
    *,
    agent_id: str,
    validator: Any,
) -> StructuredModelResponse:
    return runner.call_json(
        _prompt(payload),
        task="benchmark_c1_v5",
        agent_id=agent_id,
        validator=validator,
    )


def run_cell(
    task: dict[str, Any],
    variant: str,
    out_dir: Path,
    runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    delivery = CoordinationDeliveryChannel(out_dir / "delivery_trace.jsonl")
    slots = set(task["slots"])
    private = {agent: private_for(task, agent, variant) for agent in ("agent_a", "agent_b")}
    responses: list[StructuredModelResponse] = []
    reports: dict[str, dict[str, Any]] = {}
    for agent in ("agent_a", "agent_b"):
        delivery.put_private(agent, private[agent])
        delivery.read_private(agent, agent)
        response = _call(
            runner,
            {
                "stage": "private_report",
                "role": agent,
                "private_context": private[agent],
                "response_schema": {"agent_id": agent, "feasible": ["slot"], "preferred": "slot"},
            },
            agent_id=agent,
            validator=_validate_report(agent, slots),
        )
        responses.append(response)
        if response.ok:
            reports[agent] = response.parsed
            delivery.emit_report(agent, response.parsed)
            delivery.deliver_report(agent)
    delivered = delivery.read_reports("coordinator").get("reports") or {}
    phase1_spec = {
        "resource_id": task["resource_id"],
        "slots": task["slots"],
        "priority": task["phase1_priority"][variant],
    }
    initial_response = _call(
        runner,
        {
            "stage": "coordinator_initial",
            "role": "coordinator",
            "phase1_spec": phase1_spec,
            "delivered_reports": delivered,
            "response_schema": {"assignments": {"agent_a": "slot", "agent_b": "slot"}, "rule": RULE_ID},
        },
        agent_id="coordinator",
        validator=_validate_proposal(slots),
    )
    responses.append(initial_response)
    initial = dict(initial_response.parsed.get("assignments") or {}) if initial_response.ok else {}
    assignment = JointAssignmentChannel(
        resource_id=str(task["resource_id"]),
        slots=list(task["slots"]),
        priority=list(task["phase1_priority"][variant]),
        feasible={agent: list((delivered.get(agent) or {}).get("feasible") or []) for agent in ("agent_a", "agent_b")},
        max_retries=1,
        path=out_dir / "assignment_trace.jsonl",
    )
    saved = assignment.save_initial(initial) if initial else {"ok": False}
    initial_proposal = assignment.propose_joint_assignment("coordinator", initial) if saved.get("ok") else {"ok": False, "accepted": False}
    registered = (
        assignment.register_protection(agent=task["protection"]["agent_id"], slot=task["protection"]["slot"])
        if saved.get("ok")
        else {"ok": False}
    )
    inspection = assignment.inspect_registered_constraints() if registered.get("ok") else {"violations": []}
    violations = list(inspection.get("violations") or [])
    stale = (
        assignment.confirm_assignment(
            agent_id="agent_a",
            slot=str(initial.get("agent_a") or ""),
            plan_id=str(initial_proposal["plan_id"]),
        )
        if initial_proposal.get("plan_id") and registered.get("ok")
        else {"ok": False, "reason": "initial_plan_not_stamped"}
    )
    current_spec = {
        "status": "authoritative",
        "supersedes": "phase1_spec",
        "resource_id": task["resource_id"],
        "slots": task["slots"],
        "priority": ["agent_a", "agent_b"],
        "protected_assignment": task["protection"],
    }
    retry_response = _call(
        runner,
        {
            "stage": "coordinator_retry",
            "role": "coordinator",
            "phase1_spec": {**phase1_spec, "status": "superseded"},
            "previous_assignments": {"status": "rejected_under_current_spec", "assignments": initial},
            "authoritative_current_spec": current_spec,
            "delivered_reports": delivered,
            "platform_feedback": violations,
            "response_schema": {"assignments": {"agent_a": "slot", "agent_b": "slot"}, "rule": RULE_ID},
        },
        agent_id="coordinator",
        validator=_validate_proposal(slots),
    )
    responses.append(retry_response)
    retry = dict(retry_response.parsed.get("assignments") or {}) if retry_response.ok else {}
    final_proposal = (
        assignment.propose_joint_assignment("coordinator", retry)
        if saved.get("ok") and retry
        else {"ok": False, "accepted": False}
    )
    plan = None
    if final_proposal.get("accepted"):
        plan = {
            "plan_id": final_proposal["plan_id"],
            "spec_version": final_proposal["spec_version"],
            "assignments": retry,
            "rule": RULE_ID,
        }
        delivery.deliver_accepted_plan(plan)
    confirmations: dict[str, dict[str, Any]] = {}
    for agent in ("agent_a", "agent_b"):
        read = delivery.read_plan(agent)
        delivered_plan = read.get("plan") if read.get("ok") else None
        response = _call(
            runner,
            {
                "stage": "agent_commit",
                "role": agent,
                "private_context": private[agent],
                "delivered_platform_plan": delivered_plan,
                "response_schema": {"agent_id": agent, "confirm": "boolean", "slot": "slot_or_null"},
            },
            agent_id=agent,
            validator=_validate_commit(agent, slots),
        )
        responses.append(response)
        parsed = response.parsed if response.ok else {}
        if response.ok and parsed.get("confirm") is True and parsed.get("slot") and plan:
            confirmation = assignment.confirm_assignment(
                agent_id=agent, slot=str(parsed["slot"]), plan_id=str(plan["plan_id"])
            )
            confirmations[agent] = confirmation
            if confirmation.get("ok"):
                delivery.submit_confirmed_claim(
                    role=agent,
                    agent_id=agent,
                    slot=str(parsed["slot"]),
                    plan_id=str(plan["plan_id"]),
                    registry_confirmation=confirmation,
                )
        else:
            confirmations[agent] = {"ok": False, "reason": "agent_not_confirmed"}
    private_denial = delivery.read_private("coordinator", "agent_a")
    exec_denial = delivery.submit_confirmed_claim(
        role="coordinator",
        agent_id="agent_a",
        slot="forbidden",
        plan_id=str((plan or {}).get("plan_id") or ""),
        registry_confirmation={"ok": True},
    )
    parsed_payloads = [response.parsed for response in responses]
    model_identifier = any(
        isinstance(payload, dict) and {"plan_id", "plan_version", "spec_version"} & set(payload)
        for payload in parsed_payloads
    )
    repair_slot = task["oracle"][variant]["final"]["agent_b"]
    return {
        "task_id": task["id"],
        "variant": variant,
        "reports": delivered,
        "initial_assignments": initial,
        "initial_proposal": initial_proposal,
        "registration": registered,
        "violations": violations,
        "priority_nack_path": any(item.get("violation") == "priority_preservation_violation" for item in violations),
        "any_nack_path": bool(violations),
        "stale_confirmation": stale,
        "retry_assignments": retry,
        "final_proposal": final_proposal,
        "accepted_plan": plan,
        "confirmations": confirmations,
        "world": delivery.world_state(),
        "model_ok": [response.ok for response in responses],
        "model_errors": [response.error for response in responses],
        "model_evidence_ids": [response.evidence_id for response in responses],
        "model_generated_identifier": model_identifier,
        "nack_leaked_repair_slot": bool(violations and repair_slot in json.dumps(violations)),
        "private_isolated": private_denial.get("reason") == "unauthorized_private_read",
        "coordinator_execution_denied": exec_denial.get("reason") == "unauthorized_world_write",
        "model_summary": runner.summary(),
    }
