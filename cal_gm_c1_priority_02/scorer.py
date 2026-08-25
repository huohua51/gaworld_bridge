"""Priority-constrained reallocation scoring. World occupancy is the fact."""

from __future__ import annotations

from typing import Any

from cal_gm_c1_priority_02.loader import feasible_map, initial_assignments, oracle_plan, solve
from gaworld.work.coordination import actual_final_conflict_free
from v0_first_batch.schema import CriterionResult, GateResult, compose


def _earliest_idle(task: dict, variant: str, assignments: dict[str, str]) -> bool:
    want = solve(task, variant)
    return assignments.get("agent_b") == want.get("agent_b")


def score_cell(
    *,
    task: dict,
    variant: str,
    repeat_id: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    action = loop.get("action") or {}
    channel = loop.get("channel") or {}
    got = dict(channel.get("assignments") or action.get("assignments") or {})
    want = oracle_plan(task, variant)
    initial = initial_assignments(task, variant)
    feasible = feasible_map(task, variant)
    unregistered = int(channel.get("unregistered_modification") or 0)
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    contract_ok = bool(loop.get("contract_ok"))
    actual_free = actual_final_conflict_free(got) if got else False
    joint_sat = all(got.get(agent) in set(feasible[agent]) for agent in ("agent_a", "agent_b")) and len(got) == 2
    priority_ok = got.get("agent_a") == initial.get("agent_a")
    earliest_ok = _earliest_idle(task, variant, got)
    policy_ok = got == want == solve(task, variant)
    env_ok = bool(loop.get("env_denied"))
    no_leak = not loop.get("leaked_repair_slot_in_nack")
    correct = contract_ok and policy_ok and actual_free and joint_sat and priority_ok and earliest_ok and unregistered == 0 and env_ok and no_leak
    budget_ok = bool(loop.get("budget_valid"))
    r0 = extractable and budget_ok and int(loop.get("calls") or 0) >= 1
    conditioned = bool(r0 and correct)
    if not extractable:
        err = "fields_not_extractable"
    elif not contract_ok:
        err = str(loop.get("contract_error") or "contract_invalid")
    elif unregistered:
        err = "unregistered_modification"
    elif not no_leak:
        err = "repair_slot_leaked"
    elif not priority_ok:
        err = "priority_preservation_violation"
    elif not joint_sat:
        err = "private_infeasible"
    elif not actual_free:
        err = "final_state_conflict"
    elif not earliest_ok or not policy_ok:
        err = "not_earliest_feasible_idle"
    else:
        err = "none"
    if conditioned:
        err = "none"
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0"),
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("call_budget", budget_ok, layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("environment_did_not_rewrite", env_ok, layer="R0"),
            GateResult("repair_slot_not_in_nack", no_leak, layer="R0"),
        ],
        artifact_gates=[
            GateResult("action_exists", bool(got), layer="R1"),
            GateResult("contract_ok", contract_ok, layer="R1", detail=str(loop.get("contract_error") or "")),
            GateResult("no_unregistered_modification", unregistered == 0, layer="R1"),
        ],
        criteria=[
            CriterionResult("priority_preserved", "R2", "initial_vs_final", True, 1.0 if priority_ok else 0.0, passed=priority_ok),
            CriterionResult("earliest_idle_low", "R2", "feasible_order", True, 1.0 if earliest_ok else 0.0, passed=earliest_ok),
            CriterionResult("actual_final_conflict_free", "R2", "occupancy", True, 1.0 if actual_free else 0.0, passed=actual_free),
            CriterionResult("joint_constraint_satisfaction", "R2", "feasible_sets", True, 1.0 if joint_sat else 0.0, passed=joint_sat),
            CriterionResult("policy_constrained_plan", "R2", "oracle", True, 1.0 if policy_ok else 0.0, passed=policy_ok),
            CriterionResult("oracle_conditioned_success", "R3", "priority_component", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "contract_error": loop.get("contract_error")},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "repeat_id": repeat_id,
            "got": got,
            "want": want,
            "priority_preserved": priority_ok,
            "earliest_idle_low": earliest_ok,
            "actual_final_conflict_free": actual_free,
            "joint_constraint_satisfaction": joint_sat,
            "policy_constrained_plan": policy_ok,
            "unregistered_modification": unregistered,
            "leaked_repair_slot_in_nack": bool(loop.get("leaked_repair_slot_in_nack")),
            "first_error": err,
            "calls": loop.get("calls"),
        },
    )
    cell["ranking_eligible"] = False
    return cell


def _valid(cells: list[dict], *, variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if variant is not None and extra.get("variant") != variant:
            continue
        if cell.get("measurement_valid"):
            out.append(cell)
    return out


def _rate(cells: list[dict], *, variant: str | None = None) -> float | None:
    subset = [c for c in _valid(cells, variant=variant) if c.get("full_pass") is not None]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _mean(cells: list[dict], key: str) -> float | None:
    subset = _valid(cells)
    values = [float((c.get("extra") or {}).get(key)) for c in subset if (c.get("extra") or {}).get(key) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def coverage(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4)


def metrics(cells: list[dict]) -> dict[str, Any]:
    split = {"control": _rate(cells, variant="control"), "intervention": _rate(cells, variant="intervention")}
    rates = {
        "Coverage": coverage(cells),
        "PriorityPreserved": _mean(cells, "priority_preserved"),
        "EarliestIdleLow": _mean(cells, "earliest_idle_low"),
        "ActualFinalConflictFree": _mean(cells, "actual_final_conflict_free"),
        "JointConstraintSatisfaction": _mean(cells, "joint_constraint_satisfaction"),
        "PolicyConstrainedPlan": _mean(cells, "policy_constrained_plan"),
        "FullPass": _rate(cells),
        "UnregisteredModification": _mean(cells, "unregistered_modification"),
    }
    gate = {
        "coverage_ok": rates["Coverage"] == 1.0,
        "control_ok": split["control"] == 1.0,
        "intervention_ok": split["intervention"] == 1.0,
        "priority_ok": rates["PriorityPreserved"] == 1.0,
        "earliest_ok": rates["EarliestIdleLow"] == 1.0,
        "policy_ok": rates["PolicyConstrainedPlan"] == 1.0,
        "no_unregistered_mod": (rates["UnregisteredModification"] or 0) == 0,
    }
    gate["holds"] = all(v is True for v in gate.values())
    if gate["holds"]:
        interpretation = "优先级重试协议组件校准通过。不覆盖 C1-02 / PRIORITY-01。不开 L1，不建留出。"
    else:
        interpretation = f"优先级组件门未过。split={split}。不开 L1，不覆盖 C1-02，不建留出。"
    return {"rates": rates, "split": split, "pass_gate": gate, "interpretation": interpretation}
