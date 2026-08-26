"""Offline wiring tests for the preregistered minimal T5 pilot."""

from model_pilot.fixtures import oracle_fixture_client
from model_pilot.t5_minimal import _registration, run_registered


def test_t5_minimal_registration_hashes_and_design_are_valid() -> None:
    registration, registration_sha256 = _registration()

    assert registration["preregistration_id"] == "T5-MINIMAL-CAUSAL-GLM52-v1"
    assert len(registration_sha256) == 64


def test_t5_minimal_fixture_calibrates_registered_contrasts(tmp_path) -> None:
    summary = run_registered(
        tmp_path / "t5-minimal",
        oracle_fixture_client(),
        allow_live_model=False,
    )

    assert summary["gate"] == "offline_minimal_calibration_pass"
    assert summary["registered_design_adherent"] is True
    assert summary["all_registered_outcomes_pass"] is True
    assert summary["n_cells"] == 3
    assert summary["budget"]["calls_used"] == 12
    assert summary["FullPassByCondition"] == {
        "no_policy": 1,
        "real_policy": 1,
        "placebo_policy": 1,
    }
    assert summary["BehaviorChangeRateByCondition"] == {
        "no_policy": 0.0,
        "real_policy": 0.5,
        "placebo_policy": 0.0,
    }
    assert summary["causal_contrasts"] == {
        "real_minus_no_policy": 0.5,
        "real_minus_placebo": 0.5,
        "placebo_minus_no_policy": 0.0,
    }
    assert summary["model_contract_rate"] == 1.0
