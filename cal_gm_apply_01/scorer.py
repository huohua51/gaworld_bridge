from __future__ import annotations

from pathlib import Path
from typing import Any

from cal_gm_apply_01.inspect import field_status
from exp_gm_04.scorer import score_hidden_tests
from v0_first_batch.schema import CriterionResult, GateResult, compose

PASS_GATE = {
    "coverage": 1.0,
    "FieldAdoptionRate": 1.0,
    "CompleteChangeAdoptionRate": 1.0,
    "PartialChangeRate": 0.0,
    "UnregisteredChangeRate": 0.0,
    "HiddenTestPass": 1.0,
    "AcknowledgementExecutionGap": 0.0,
}


def _reread(path: str | None) -> str:
    if not path:
        return ""
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    return file_path.read_text(encoding="utf-8")


def score_cell(
    *,
    task: dict,
    variant: str,
    repeat_id: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    final_path = str(loop.get("final_path") or "")
    source = _reread(final_path)
    status = field_status(task, variant, source)
    control_oracle = score_hidden_tests(final_path, task["oracle_control"])
    intervention_oracle = score_hidden_tests(final_path, task["oracle_intervention"])
    if variant == "control":
        hidden = bool(control_oracle.get("passed")) and not bool(intervention_oracle.get("passed"))
    else:
        hidden = bool(intervention_oracle.get("passed")) and not bool(control_oracle.get("passed"))
    ack_gap = bool(status["declared"]) and not bool(status["complete"])
    extractable = bool(source.strip())
    r0 = extractable and bool(loop.get("budget_valid")) and loop.get("calls") == 1 and bool(final_path)
    complete = bool(status["complete"])
    if not extractable:
        err = "fields_not_extractable"
    elif status["unregistered"]:
        err = "unregistered_change"
    elif status["partial"]:
        err = "partial_change_applied"
    elif ack_gap:
        err = "change_acknowledged_not_applied"
    elif status["missed"] and not status["adopted"]:
        err = "required_change_not_read"
    elif not hidden:
        err = "final_hidden_test_failed"
    else:
        err = "none"
    if complete and hidden and not ack_gap:
        err = "none"
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0"),
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("single_call", loop.get("calls") == 1, layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("artifact_on_disk", Path(final_path).is_file() if final_path else False, layer="R0"),
        ],
        artifact_gates=[
            GateResult("reviewer_is_rule", bool(loop.get("reviewer_is_rule")), layer="R1"),
            GateResult("environment_did_not_rewrite", not loop.get("environment_rewrote"), layer="R1"),
        ],
        criteria=[
            CriterionResult("complete_adoption", "R2", "file_values", True, 1.0 if complete else 0.0, passed=complete, critical=True),
            CriterionResult("hidden_test_pass", "R2", "hidden_oracle", True, 1.0 if hidden else 0.0, passed=hidden, critical=True),
        ],
        process_profile={"first_error": err, "field_status": status},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "repeat_id": repeat_id,
            "adopted_n": status["adopted_n"],
            "required_n": status["required_n"],
            "complete": complete,
            "partial": bool(status["partial"]),
            "unregistered": bool(status["unregistered"]),
            "hidden_test_pass": hidden,
            "acknowledgement_execution_gap": ack_gap,
            "declared": bool(status["declared"]),
            "got": status["got"],
            "first_error": err,
            "control_oracle": bool(control_oracle.get("passed")),
            "intervention_oracle": bool(intervention_oracle.get("passed")),
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


def coverage(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4)


def field_adoption_rate(cells: list[dict]) -> float | None:
    adopted = 0
    required = 0
    for cell in _valid(cells):
        extra = cell.get("extra") or {}
        adopted += int(extra.get("adopted_n") or 0)
        required += int(extra.get("required_n") or 0)
    if required == 0:
        return None
    return round(adopted / required, 4)


def _mean_flag(cells: list[dict], field: str) -> float | None:
    subset = _valid(cells)
    if not subset:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in subset) / len(subset), 4)


def metrics(cells: list[dict]) -> dict[str, Any]:
    rates = {
        "Coverage": coverage(cells),
        "FieldAdoptionRate": field_adoption_rate(cells),
        "CompleteChangeAdoptionRate": _mean_flag(cells, "complete"),
        "PartialChangeRate": _mean_flag(cells, "partial"),
        "UnregisteredChangeRate": _mean_flag(cells, "unregistered"),
        "HiddenTestPass": _mean_flag(cells, "hidden_test_pass"),
        "AcknowledgementExecutionGap": _mean_flag(cells, "acknowledgement_execution_gap"),
    }
    gate = {
        "coverage_ok": rates["Coverage"] == PASS_GATE["coverage"],
        "field_ok": rates["FieldAdoptionRate"] == PASS_GATE["FieldAdoptionRate"],
        "complete_ok": rates["CompleteChangeAdoptionRate"] == PASS_GATE["CompleteChangeAdoptionRate"],
        "partial_ok": rates["PartialChangeRate"] == PASS_GATE["PartialChangeRate"],
        "unregistered_ok": rates["UnregisteredChangeRate"] == PASS_GATE["UnregisteredChangeRate"],
        "hidden_ok": rates["HiddenTestPass"] == PASS_GATE["HiddenTestPass"],
        "ack_ok": rates["AcknowledgementExecutionGap"] == PASS_GATE["AcknowledgementExecutionGap"],
    }
    gate["holds"] = all(gate.values()) and all(v is not None for v in rates.values())
    return {"rates": rates, "pass_gate": gate}
