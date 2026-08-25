from __future__ import annotations

from typing import Any

from cal_gm_c1_comp_01.contract import A_KEY, B_KEY
from cal_gm_c1_comp_01.loader import final_conflict_free, initial_conflict, oracle_value, solve_reallocate
from v0_first_batch.schema import CriterionResult, GateResult, compose


def _scorer_fact(task: dict, variant: str) -> Any:
    if task["component"] == "A":
        return initial_conflict(task, variant)
    if task["component"] == "B":
        return final_conflict_free(task, variant)
    return solve_reallocate(task, variant)


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
    fact = _scorer_fact(task, variant)
    want = oracle_value(task, variant)
    component = task["component"]
    if component == "A":
        got = action.get(A_KEY)
        correct = contract_ok and got is fact is want
        err_wrong = "initial_conflict_incorrect"
    elif component == "B":
        got = action.get(B_KEY)
        correct = contract_ok and got is fact is want
        err_wrong = "final_conflict_free_incorrect"
    else:
        got = action.get("assignments")
        correct = contract_ok and got == fact == want
        err_wrong = "allocation_incorrect"
    r0 = extractable and bool(loop.get("budget_valid")) and loop.get("calls") == 1
    conditioned = bool(r0 and contract_ok and correct)
    if not extractable:
        err = "fields_not_extractable"
    elif not contract_ok:
        err = str(loop.get("contract_error") or "contract_invalid")
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
            GateResult("single_call", loop.get("calls") == 1, layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult("action_exists", bool(action), layer="R1"),
            GateResult("contract_ok", contract_ok, layer="R1", detail=str(loop.get("contract_error") or "")),
        ],
        criteria=[
            CriterionResult("component_correct", "R2", "c1comp_oracle", True, 1.0 if correct else 0.0, passed=correct),
            CriterionResult("oracle_conditioned_success", "R3", "c1comp_oracle", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
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


def _rate(cells: list[dict], *, component: str | None = None) -> float | None:
    subset = [c for c in _valid(cells, component=component) if c.get("full_pass") is not None]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def coverage(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4)


def interpret(cells: list[dict]) -> str:
    detect = _rate(cells, component="A")
    verify = _rate(cells, component="B")
    alloc = _rate(cells, component="C")
    detect_ok = detect == 1.0 and verify == 1.0
    alloc_ok = alloc == 1.0
    if detect_ok is False and alloc_ok:
        return "会安排，但不会稳定表达或识别初始冲突"
    if detect_ok and not alloc_ok:
        return "能发现冲突，但不会按规则形成新方案"
    if detect_ok and alloc_ok:
        return "两者都通过：单组件会做。可以建立 C1-02。C1-01 Direct 失败应视为完整上下文接口集成退化。"
    if (detect or 0) == 0 and (verify or 0) == 0 and (alloc or 0) == 0:
        return "两者都失败：Direct 真实能力地板，暂时停止 C1"
    return f"检测A={detect} 核验B={verify} 分配C={alloc}。按组件分别解释，不合并成分。"


def metrics(cells: list[dict]) -> dict[str, Any]:
    rates = {
        "Coverage": coverage(cells),
        "A_initial_conflict": _rate(cells, component="A"),
        "B_final_conflict_free": _rate(cells, component="B"),
        "C_reallocate": _rate(cells, component="C"),
    }
    gate = {
        "coverage_ok": rates["Coverage"] == 1.0,
        "a_ok": rates["A_initial_conflict"] == 1.0,
        "b_ok": rates["B_final_conflict_free"] == 1.0,
        "c_ok": rates["C_reallocate"] == 1.0,
    }
    gate["holds"] = all(v is True for v in gate.values())
    return {"rates": rates, "pass_gate": gate, "interpretation": interpret(cells)}
