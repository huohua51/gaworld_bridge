from __future__ import annotations

from typing import Any

from cal_gm_change_01.contract import KEEP, UPDATE
from cal_gm_change_01.loader import required_value
from v0_first_batch.schema import CriterionResult, GateResult, compose

PASS_GATE = {
    "coverage": 1.0,
    "KeepAccuracy": 1.0,
    "UpdateAccuracy": 1.0,
    "EvidenceGroundingRate": 1.0,
}


def _num(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def evidence_grounded(task: dict, variant: str, action: dict[str, Any]) -> bool:
    evidence = action.get("evidence") or {}
    observed = _num(evidence.get("observed"))
    required = _num(evidence.get("required"))
    want_required = required_value(task, variant)
    if evidence.get("path") != task["path"]:
        return False
    if observed != int(task["current"]):
        return False
    if required != want_required:
        return False
    if action.get("decision") == KEEP:
        return observed == required and action.get("required_change") is None
    change = action.get("required_change") or {}
    return (
        action.get("decision") == UPDATE
        and change.get("path") == task["path"]
        and _num(change.get("old_value")) == int(task["current"])
        and _num(change.get("new_value")) == want_required
    )


def decision_correct(task: dict, variant: str, action: dict[str, Any]) -> bool:
    want = KEEP if variant == "control" else UPDATE
    return action.get("decision") == want


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
    grounded = evidence_grounded(task, variant, action) if contract_ok else False
    correct = decision_correct(task, variant, action) if contract_ok else False
    fp = variant == "control" and action.get("decision") == UPDATE
    missed = variant == "intervention" and action.get("decision") == KEEP
    r0 = extractable and bool(loop.get("budget_valid")) and loop.get("calls") == 1
    conditioned = bool(r0 and contract_ok and correct and grounded)
    if not extractable:
        err = "fields_not_extractable"
    elif not contract_ok:
        err = str(loop.get("contract_error") or "decision_contract_invalid")
    elif fp:
        err = "false_positive_revision"
    elif missed:
        err = "missed_revision"
    elif not grounded:
        err = "evidence_not_grounded"
    elif not correct:
        err = "decision_incorrect"
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
            GateResult("decision_exists", bool(action.get("decision")), layer="R1"),
            GateResult("contract_ok", contract_ok, layer="R1", detail=str(loop.get("contract_error") or "")),
        ],
        criteria=[
            CriterionResult("keep_or_update_correct", "R2", "change_oracle", True, 1.0 if correct else 0.0, passed=correct),
            CriterionResult("evidence_grounded", "R2", "change_oracle", True, 1.0 if grounded else 0.0, passed=grounded),
            CriterionResult("oracle_conditioned_success", "R3", "change_oracle", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "contract_error": loop.get("contract_error")},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "repeat_id": repeat_id,
            "keep_correct": variant == "control" and correct,
            "update_correct": variant == "intervention" and correct,
            "evidence_grounded": grounded,
            "false_positive_revision": fp,
            "missed_revision": missed,
            "decision": action.get("decision"),
            "action": action,
            "first_error": err,
        },
    )
    cell["ranking_eligible"] = False
    return cell


def _valid(cells: list[dict], variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if variant is not None and extra.get("variant") != variant:
            continue
        if cell.get("measurement_valid"):
            out.append(cell)
    return out


def _subset(cells: list[dict], variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if variant is not None and extra.get("variant") != variant:
            continue
        out.append(cell)
    return out


def _mean_flag(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in cells) / len(cells), 4)


def coverage(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4)


def keep_accuracy(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells, "control"), "keep_correct")


def update_accuracy(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells, "intervention"), "update_correct")


def evidence_grounding_rate(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells), "evidence_grounded")


def false_positive_revision_rate(cells: list[dict]) -> float | None:
    control = _subset(cells, "control")
    if not control:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get("false_positive_revision"))) for c in control) / len(control), 4)


def missed_revision_rate(cells: list[dict]) -> float | None:
    intervention = _subset(cells, "intervention")
    if not intervention:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get("missed_revision"))) for c in intervention) / len(intervention), 4)


def strict_pair(cells: list[dict]) -> float | None:
    groups: dict[tuple[Any, Any], dict[str, dict]] = {}
    for cell in cells:
        extra = cell.get("extra") or {}
        key = (extra.get("task_id"), extra.get("repeat_id"))
        groups.setdefault(key, {})[str(extra.get("variant"))] = cell
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    n_ok = 0
    for pair in pairs:
        if pair["control"].get("full_pass") == 1 and pair["intervention"].get("full_pass") == 1:
            n_ok += 1
    return round(n_ok / len(pairs), 4)


def control_all_false_positive(cells: list[dict]) -> bool:
    control = _subset(cells, "control")
    return bool(control) and all(bool((c.get("extra") or {}).get("false_positive_revision")) for c in control)


def metrics(cells: list[dict]) -> dict[str, Any]:
    rates = {
        "Coverage": coverage(cells),
        "KeepAccuracy": keep_accuracy(cells),
        "UpdateAccuracy": update_accuracy(cells),
        "FalsePositiveRevisionRate": false_positive_revision_rate(cells),
        "MissedRevisionRate": missed_revision_rate(cells),
        "EvidenceGroundingRate": evidence_grounding_rate(cells),
        "StrictPair": strict_pair(cells),
    }
    gate = {
        "coverage_ok": rates["Coverage"] == PASS_GATE["coverage"],
        "keep_ok": rates["KeepAccuracy"] == PASS_GATE["KeepAccuracy"],
        "update_ok": rates["UpdateAccuracy"] == PASS_GATE["UpdateAccuracy"],
        "grounding_ok": rates["EvidenceGroundingRate"] == PASS_GATE["EvidenceGroundingRate"],
    }
    gate["holds"] = all(gate.values()) and all(v is not None for v in rates.values())
    return {"rates": rates, "pass_gate": gate, "control_all_false_positive": control_all_false_positive(cells)}
