from benchmark_core.eval_mode import (
    capture_eval_mode_evidence,
    validate_eval_mode_evidence,
)


def test_capture_eval_mode_records_effective_runtime_state() -> None:
    config = {
        "eval_mode": {"enabled": True},
        "dynamic_behavior": {"enabled": True},
        "routine_change": {"enabled": True},
    }

    evidence = capture_eval_mode_evidence(config)

    assert validate_eval_mode_evidence(evidence) == (True, "ok")
    assert config["dynamic_behavior"]["enabled"] is False
    assert config["routine_change"]["enabled"] is False


def test_disabled_or_unapplied_eval_mode_fails_r0() -> None:
    disabled = capture_eval_mode_evidence({"eval_mode": {"enabled": False}})
    passed, detail = validate_eval_mode_evidence(disabled)

    assert passed is False
    assert "eval_mode_disabled" in detail
    assert "eval_mode_not_applied" in detail


def test_missing_eval_mode_evidence_fails_r0() -> None:
    assert validate_eval_mode_evidence(None) == (False, "eval_mode_evidence_missing")
