"""Offline calibration for the joint T5-v3 sealed cross-model runner."""

from __future__ import annotations

from model_pilot.t5_v3_cross_fixture import oracle_fixture_clients
from model_pilot.t5_v3_sealed_cross_model import _registration, run_registered


def test_t5_v3_sealed_cross_model_registration_is_valid() -> None:
    registration, registration_sha256 = _registration()

    assert registration["preregistration_id"] == "T5-V3-SEALED-CROSS-MODEL-v1"
    assert registration["design"]["model_keys"] == ["glm52", "gpt54"]
    assert len(registration_sha256) == 64


def test_t5_v3_sealed_cross_model_fixture_calibrates_joint_oracle(tmp_path) -> None:
    summary = run_registered(
        tmp_path / "sealed-cross-model",
        oracle_fixture_clients(),
        allow_live_model=False,
    )

    assert summary["gate"] == "offline_sealed_cross_model_calibration_pass"
    assert summary["registered_design_adherent"] is True
    assert summary["all_registered_outcomes_pass"] is True
    assert summary["n_cells"] == 18
    assert summary["total_calls"] == 72
    assert summary["cross_model_exact_agreement_rate"] == 1.0
    assert summary["cross_model_prompt_identity_rate"] == 1.0
    for model_key in ("glm52", "gpt54"):
        model = summary["per_model"][model_key]
        assert model["all_registered_outcomes_pass"] is True
        assert model["n_cells"] == 9
        assert model["budget"]["calls_used"] == 36
        assert model["FullPassByPolicyState"] == {
            "absence": 1.0,
            "binding": 1.0,
            "nonbinding": 1.0,
        }
        assert model["BehaviorChangeRateByPolicyState"] == {
            "absence": 0.0,
            "binding": 0.5,
            "nonbinding": 0.0,
        }
        assert model["scope_semantics_rate"] == 1.0
        assert model["resident_directive_rate"] == 1.0
        assert model["policy_response_rate"] == 1.0
    assert all(
        item["prompt_identical_across_models"]
        and item["outcome_exact_agreement"]
        for item in summary["by_task_policy_state"].values()
    )
