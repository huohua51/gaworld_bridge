from v0_first_batch.schema import CriterionResult, GateResult, compose
from v0_first_batch.workflows import (
    capability_quiz,
    causal_diagnostic,
    compare_event_unique_path,
    contract_interview,
    eval_mode_environment,
    life_history_mock,
    structured_action_pairs,
    work_artifact_r1,
)


def _cell(summary: dict, instance_id: str) -> dict:
    return next(item for item in summary["cells"] if item["instance_id"] == instance_id)


def test_compose_failure_cannot_keep_first_error_none() -> None:
    result = compose(
        workflow_id="t",
        instance_id="gap",
        measurement_gates=[GateResult("m", True)],
        artifact_gates=[],
        criteria=[CriterionResult("c", "R2", "exact", True, 0.0, passed=False, critical=True)],
        process_profile={"first_error": "none"},
    )
    assert result["full_pass"] == 0
    assert result["process_profile"]["first_error"] == "unexplained_failure"
    assert result["extra"]["first_error_enumerator_gap"] is True
    result = compose(
        workflow_id="t",
        instance_id="x",
        measurement_gates=[GateResult("m", False)],
        artifact_gates=[],
        criteria=[CriterionResult("c", "R2", "exact", True, 1.0, passed=True)],
    )
    assert result["status"] == "measurement_invalid"
    assert result["full_pass"] is None
    assert result["task_score"] is None


def test_interview_valid_passes_and_prose_fails() -> None:
    summary = contract_interview.run()
    assert _cell(summary, "valid_object_json")["full_pass"] == 1
    assert _cell(summary, "valid_pair_array_json")["full_pass"] == 1
    assert _cell(summary, "prose_no_json")["full_pass"] == 0
    assert _cell(summary, "runtime_prose_fallback")["full_pass"] == 0


def test_work_r1_rejects_placeholder_and_reference_copy() -> None:
    summary = work_artifact_r1.run()
    assert _cell(summary, "content_ok")["full_pass"] == 1
    assert _cell(summary, "content_placeholder")["full_pass"] == 0
    assert _cell(summary, "content_copy_reference")["full_pass"] == 0
    assert _cell(summary, "code_syntax_fail")["full_pass"] == 0


def test_unique_path_audit_invalidates_spillover() -> None:
    summary = compare_event_unique_path.run()
    assert _cell(summary, "unique_path_only")["full_pass"] == 1
    spill = _cell(summary, "spillover_unregistered_metrics")
    assert spill["measurement_valid"] is False
    assert _cell(summary, "null_no_change")["full_pass"] == 1


def test_causal_suite_capable_vs_locked() -> None:
    summary = causal_diagnostic.run()
    assert _cell(summary, "capable_traces")["full_pass"] == 1
    assert _cell(summary, "locked_yes_traces")["full_pass"] == 0
    missing = _cell(summary, "missing_target_action")
    assert missing["measurement_valid"] is False


def test_human_and_quiz_are_not_rankable() -> None:
    human = life_history_mock.run()
    quiz = capability_quiz.run()
    env = eval_mode_environment.run()
    assert human["ranking_eligible"] is False
    assert quiz["ranking_eligible"] is False
    assert _cell(env, "current_default_config")["full_pass"] == 0
    assert _cell(env, "eval_mode_enabled_runtime")["full_pass"] == 1


def test_structured_action_pairs_capable_vs_locked() -> None:
    summary = structured_action_pairs.run()
    assert _cell(summary, "capable_structured_json")["full_pass"] == 1
    assert _cell(summary, "locked_structured_json")["full_pass"] == 0
    assert _cell(summary, "prose_no_action")["measurement_valid"] is False
