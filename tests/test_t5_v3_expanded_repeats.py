"""Offline calibration for expanded T5-v3 three-model repeats."""

from __future__ import annotations

from model_pilot.t5_v3_expanded_fixture import oracle_fixture_clients
from model_pilot.t5_v3_expanded_repeats import _registration, run_registered


def test_expanded_three_model_repeat_registration_is_valid() -> None:
    registration, registration_sha256 = _registration()

    assert registration["preregistration_id"] == ("T5-V3-EXPANDED-3MODEL-REPEAT-v1")
    assert registration["design"]["model_keys"] == [
        "glm52",
        "gpt54",
        "qwen37plus",
    ]
    assert registration["design"]["seeds"] == [0, 1]
    assert len(registration_sha256) == 64


def test_expanded_three_model_repeat_fixture_calibrates_oracle(tmp_path) -> None:
    summary = run_registered(
        tmp_path / "expanded-three-model-repeats",
        oracle_fixture_clients(),
        allow_live_model=False,
    )

    assert summary["gate"] == ("offline_expanded_three_model_repeat_calibration_pass")
    assert summary["registered_design_adherent"] is True
    assert summary["all_registered_outcomes_pass"] is True
    assert summary["n_cells"] == 72
    assert summary["total_calls"] == 288
    assert summary["cross_model_exact_agreement_rate"] == 1.0
    assert summary["cross_model_prompt_identity_rate"] == 1.0
    assert summary["repeat_exact_agreement_rate"] == 1.0
    assert summary["repeat_prompt_identity_rate"] == 1.0
    for model_key in ("glm52", "gpt54", "qwen37plus"):
        model = summary["per_model"][model_key]
        assert model["all_registered_outcomes_pass"] is True
        assert model["n_cells"] == 24
        assert model["budget"]["calls_used"] == 96
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
