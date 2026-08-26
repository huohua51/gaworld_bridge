"""Strict cell composition for new functional benchmark experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from benchmark_core.eval_mode import eval_mode_gate
from benchmark_core.task_card import TASK_FAMILIES
from v0_first_batch.schema import CriterionResult, GateResult, compose


@dataclass(frozen=True)
class RunContext:
    run_id: str
    task_id: str
    task_family: str
    mechanism_condition: str
    variant: str
    seed: int
    track: str
    model_version: str
    temperature: float
    budget: int | float | dict[str, Any]
    environment_version: str
    trace_version: str
    scorer_version: str
    evidence_id: str

    def validation_errors(self) -> list[str]:
        errors: list[str] = []
        payload = asdict(self)
        for key, value in payload.items():
            if key in {"seed", "temperature", "budget"}:
                continue
            if not str(value).strip():
                errors.append(f"run_context_missing:{key}")
        if self.task_family not in TASK_FAMILIES:
            errors.append(f"run_context_invalid_task_family:{self.task_family}")
        return errors


def _evidence_errors(criteria: list[CriterionResult]) -> list[str]:
    return [
        f"critical_evidence_missing:{criterion.criterion_id}"
        for criterion in criteria
        if criterion.critical and criterion.evaluable and not criterion.evidence_ids
    ]


def compose_cell(
    *,
    workflow_id: str,
    context: RunContext,
    eval_mode_evidence: dict[str, Any] | None,
    measurement_gates: list[GateResult],
    artifact_gates: list[GateResult],
    criteria: list[CriterionResult],
    process_profile: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
    result_kind: Literal["capability", "diagnostic"] = "capability",
) -> dict[str, Any]:
    """Compose a cell while enforcing context, evidence and eval-mode gates."""

    context_errors = context.validation_errors()
    evidence_errors = _evidence_errors(criteria)
    critical = [
        criterion
        for criterion in criteria
        if criterion.critical and criterion.evaluable
    ]
    if result_kind == "capability" and not critical:
        evidence_errors.append("critical_capability_criterion_missing")

    strict_measurement = [
        *measurement_gates,
        eval_mode_gate(eval_mode_evidence),
        GateResult(
            "run_context_complete",
            not context_errors,
            critical=True,
            layer="R0",
            detail="ok" if not context_errors else ",".join(context_errors),
        ),
        GateResult(
            "critical_evidence_bound",
            not evidence_errors,
            critical=True,
            layer="R0",
            detail="ok" if not evidence_errors else ",".join(evidence_errors),
        ),
    ]
    merged_extra = dict(extra or {})
    merged_extra["run_context"] = asdict(context)
    merged_extra["eval_mode_evidence"] = dict(eval_mode_evidence or {})

    cell = compose(
        workflow_id=workflow_id,
        instance_id=context.run_id,
        measurement_gates=strict_measurement,
        artifact_gates=artifact_gates,
        criteria=criteria,
        process_profile=process_profile,
        extra=merged_extra,
    )
    if result_kind == "diagnostic" and cell.get("measurement_valid"):
        cell["full_pass"] = None
        cell["ranking_eligible"] = False
        cell["status"] = "diagnostic_only"
    return cell
