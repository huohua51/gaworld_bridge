from benchmark_core.result import RunContext, compose_cell
from v0_first_batch.schema import CriterionResult, GateResult


def _context(**overrides) -> RunContext:
    values = {
        "run_id": "run-1",
        "task_id": "task-1",
        "task_family": "T3",
        "mechanism_condition": "M3-full",
        "variant": "control",
        "seed": 0,
        "track": "full",
        "model_version": "rule",
        "temperature": 0,
        "budget": 3,
        "environment_version": "env-1",
        "trace_version": "trace-1",
        "scorer_version": "scorer-1",
        "evidence_id": "bundle-1",
    }
    values.update(overrides)
    return RunContext(**values)


def _eval_evidence() -> dict:
    return {
        "enabled": True,
        "applied": True,
        "changes": [],
        "dynamic_behavior_enabled": False,
        "routine_change_enabled": False,
        "strict_interview_json": True,
        "diary_fallback_disabled": True,
    }


def test_capability_cell_requires_critical_evidence_binding() -> None:
    result = compose_cell(
        workflow_id="workflow",
        context=_context(),
        eval_mode_evidence=_eval_evidence(),
        measurement_gates=[GateResult("execution_valid", True)],
        artifact_gates=[],
        criteria=[
            CriterionResult(
                "success",
                "R2",
                "oracle",
                True,
                1.0,
                passed=True,
                critical=True,
            )
        ],
    )

    assert result["measurement_valid"] is False
    assert result["full_pass"] is None
    gate = next(
        item for item in result["gates"] if item["gate_id"] == "critical_evidence_bound"
    )
    assert gate["passed"] is False


def test_complete_capability_cell_passes() -> None:
    result = compose_cell(
        workflow_id="workflow",
        context=_context(),
        eval_mode_evidence=_eval_evidence(),
        measurement_gates=[GateResult("execution_valid", True)],
        artifact_gates=[GateResult("artifact_present", True, layer="R1")],
        criteria=[
            CriterionResult(
                "success",
                "R2",
                "oracle",
                True,
                1.0,
                passed=True,
                critical=True,
                evidence_ids=["bundle-1:result"],
            )
        ],
    )

    assert result["measurement_valid"] is True
    assert result["full_pass"] == 1
    assert result["extra"]["run_context"]["task_family"] == "T3"
    assert result["extra"]["eval_mode_evidence"]["applied"] is True


def test_diagnostic_cell_never_becomes_fullpass() -> None:
    result = compose_cell(
        workflow_id="workflow",
        context=_context(),
        eval_mode_evidence=_eval_evidence(),
        measurement_gates=[GateResult("execution_valid", True)],
        artifact_gates=[],
        criteria=[],
        result_kind="diagnostic",
    )

    assert result["measurement_valid"] is True
    assert result["full_pass"] is None
    assert result["ranking_eligible"] is False
    assert result["status"] == "diagnostic_only"
