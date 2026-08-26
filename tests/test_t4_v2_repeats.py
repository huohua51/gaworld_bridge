"""Offline wiring tests for the preregistered T4-v2 repeats."""

from model_pilot.fixtures import oracle_fixture_client
from model_pilot.t4_v2_repeats import _registration, run_registered


def test_t4_v2_repeat_registration_hashes_and_design_are_valid() -> None:
    registration, registration_sha256 = _registration()

    assert registration["preregistration_id"] == (
        "T4-REGISTERED-TRANSPORT-GLM52-REPEATS-v1"
    )
    assert len(registration_sha256) == 64


def test_t4_v2_repeat_fixture_combines_seed0_1_2(tmp_path) -> None:
    summary = run_registered(
        tmp_path / "t4-v2-repeats",
        oracle_fixture_client(),
        allow_live_model=False,
    )

    assert summary["gate"] == "offline_repeat_calibration_pass"
    assert summary["registered_design_adherent"] is True
    assert summary["all_registered_outcomes_pass"] is True
    assert summary["new_cells"] == 12
    assert summary["combined_cells"] == 18
    assert summary["budget"]["calls_used"] == 48
    assert summary["pooled_seed0_1_2"]["source_forward_rate"] == 1.0
    assert summary["pooled_seed0_1_2"]["complete_path_rate"] == 1.0
    assert summary["pooled_seed0_1_2"]["target_acceptance_rate"] == 1.0
    assert summary["pooled_seed0_1_2"]["full_pass_rate"] == 1.0
    assert all(
        item["prompt_stable_across_seed0_1_2"]
        for item in summary["by_task_variant"].values()
    )
