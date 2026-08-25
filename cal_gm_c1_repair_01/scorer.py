from __future__ import annotations

from typing import Any

from cal_gm_c1_repair_01.contract import A_KEY, B_KEY
from cal_gm_c1_repair_01.loader import given_final, initial_conflict, oracle_value, solve_reallocate
from gaworld.work.coordination import actual_final_conflict_free
from v0_first_batch.schema import CriterionResult, GateResult, compose


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
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    contract_ok = bool(loop.get("contract_ok"))
    component = task["component"]
    want = oracle_value(task, variant)
    channel = loop.get("channel") or {}
    unregistered = int(channel.get("unregistered_modification") or 0)
    if component == "A":
        fact = initial_conflict(task, variant)
        got = action.get(A_KEY)
        self_ok = contract_ok and got is fact is want
        actual_free = None
        err_wrong = "initial_conflict_incorrect"
        correct = self_ok
    elif component == "B":
        plan = given_final(task, variant)
        fact = actual_final_conflict_free(plan)
        got = action.get(B_KEY)
        self_ok = contract_ok and got is fact is want
        actual_free = fact
        err_wrong = "self_assessment_incorrect"
        correct = self_ok
    else:
        fact = solve_reallocate(task, variant)
        got = channel.get("assignments") or action.get("assignments")
        actual_free = bool(channel.get("actual_final_conflict_free"))
        if actual_free is False and got:
            actual_free = actual_final_conflict_free(got)
        alloc_ok = contract_ok and got == fact == want
        self_ok = alloc_ok
        correct = alloc_ok and actual_free is True and unregistered == 0
        err_wrong = "allocation_incorrect"
        if alloc_ok and unregistered:
            err_wrong = "unregistered_modification"
        elif alloc_ok and actual_free is not True:
            err_wrong = "final_world_still_conflicted"
    budget_ok = bool(loop.get("budget_valid"))
    call_ok = int(loop.get("calls") or 0) >= 1 and int(loop.get("calls") or 0) <= (2 if component == "C" else 1)
    r0 = extractable and budget_ok and call_ok
    conditioned = bool(r0 and contract_ok and correct)
    if not extractable:
        err = "fields_not_extractable"
    elif not contract_ok:
        err = str(loop.get("contract_error") or "contract_invalid")
    elif unregistered:
        err = "unregistered_modification"
    elif not correct:
        err = err_wrong
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
            GateResult("call_budget", call_ok, layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult("action_exists", bool(action) or bool(got), layer="R1"),
            GateResult("contract_ok", contract_ok, layer="R1", detail=str(loop.get("contract_error") or "")),
            GateResult("no_unregistered_modification", unregistered == 0, layer="R1"),
        ],
        criteria=[
            CriterionResult("component_correct", "R2", "c1repair_oracle", True, 1.0 if correct else 0.0, passed=correct),
            CriterionResult("oracle_conditioned_success", "R3", "c1repair_oracle", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "contract_error": loop.get("contract_error"), "scorer_fact": fact},
        extra={
            "task_id": task["id"],
            "component": component,
            "variant": variant,
            "repeat_id": repeat_id,
            "correct": correct,
            "got": got,
            "want": want,
            "scorer_fact": fact,
            "self_assessment_correct": self_ok if component == "B" else None,
            "actual_final_conflict_free": actual_free,
            "assessment_execution_gap": (None if component != "B" else int(not self_ok)),
            "unregistered_modification": unregistered,
            "action": action,
            "first_error": err,
        },
    )
    cell["ranking_eligible"] = False
    return cell


def _valid(cells: list[dict], *, component: str | None = None, variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if component is not None and extra.get("component") != component:
            continue
        if variant is not None and extra.get("variant") != variant:
            continue
        if cell.get("measurement_valid"):
            out.append(cell)
    return out


def _rate(cells: list[dict], *, component: str | None = None, variant: str | None = None) -> float | None:
    subset = [c for c in _valid(cells, component=component, variant=variant) if c.get("full_pass") is not None]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _mean_extra(cells: list[dict], key: str, *, component: str | None = None) -> float | None:
    subset = _valid(cells, component=component)
    values = []
    for cell in subset:
        extra = cell.get("extra") or {}
        if extra.get(key) is None:
            continue
        values.append(float(extra[key]))
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def coverage(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4)


def metrics(cells: list[dict]) -> dict[str, Any]:
    split = {
        "A_control": _rate(cells, component="A", variant="control"),
        "A_intervention": _rate(cells, component="A", variant="intervention"),
        "B_control": _rate(cells, component="B", variant="control"),
        "B_intervention": _rate(cells, component="B", variant="intervention"),
        "C_control": _rate(cells, component="C", variant="control"),
        "C_intervention": _rate(cells, component="C", variant="intervention"),
    }
    rates = {
        "Coverage": coverage(cells),
        "A_initial_conflict": _rate(cells, component="A"),
        "B_self_assessment_correct": _rate(cells, component="B"),
        "C_reallocate": _rate(cells, component="C"),
        "ActualFinalConflictFree": _mean_extra(cells, "actual_final_conflict_free", component="C"),
        "UnregisteredModification": _mean_extra(cells, "unregistered_modification"),
        "AssessmentExecutionGap": _mean_extra(cells, "assessment_execution_gap", component="B"),
    }
    gate = {
        "coverage_ok": rates["Coverage"] == 1.0,
        "a_ok": split["A_control"] == 1.0 and split["A_intervention"] == 1.0,
        "b_strict_pair": split["B_control"] == 1.0 and split["B_intervention"] == 1.0,
        "c_strict_pair": split["C_control"] == 1.0 and split["C_intervention"] == 1.0,
        "actual_final_free_ok": rates["ActualFinalConflictFree"] == 1.0,
        "no_unregistered_mod": (rates["UnregisteredModification"] or 0) == 0,
    }
    gate["holds"] = all(v is True for v in gate.values())
    c1_02 = bool(gate["holds"])
    if gate["holds"]:
        interpretation = "组件复测全部通过。c1_02_allowed=true。仍不开 L1，不改 C1-01。"
    else:
        interpretation = (
            f"组件门未过。split={split} ActualFinalConflictFree={rates['ActualFinalConflictFree']}。"
            " c1_02_allowed 保持 false。不开 L1，不改 C1-01，不跑 Multi。"
        )
    return {
        "rates": rates,
        "split": split,
        "pass_gate": gate,
        "c1_02_allowed": c1_02,
        "interpretation": interpretation,
    }
