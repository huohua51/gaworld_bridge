from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "human_validity" / "MASTER_PLAN.yaml"
PREREG = ROOT / "human_validity" / "h1_h4_v2" / "PREREGISTRATION.yaml"


def _load(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_master_plan_keeps_all_h_dimensions_separate() -> None:
    plan = _load(MASTER)
    assert set(plan["dimensions"]) == {f"H{index}" for index in range(1, 8)}
    assert plan["global_rules"]["no_cross_dimension_total_score"] is True
    assert plan["global_rules"]["missing_matched_human_reference"] == "N/A"
    assert plan["global_rules"]["current_exp_hf_h1_01_is_pipeline_pilot_only"] is True
    assert len(plan["human_reference_gates"]) == 8


def test_master_plan_does_not_claim_unmeasured_dimensions() -> None:
    plan = _load(MASTER)
    assert plan["dimensions"]["H1"]["current_status"] == "partial_pipeline_only"
    assert plan["dimensions"]["H4"]["current_status"] == "partial_protocol_pipeline_only"
    for dimension in ("H2", "H3", "H5", "H6", "H7"):
        assert plan["dimensions"][dimension]["current_status"] == "N/A"


def test_h1_h4_v2_is_blocked_before_formal_collection() -> None:
    prereg = _load(PREREG)
    assert prereg["status"] == "draft_pre_data"
    assert prereg["formal_data_collection_allowed"] is False
    assert set(prereg["target_axes"]) == {"H1", "H4"}
    assert set(prereg["scope"]["explicitly_not_measured"]) == {
        "H2",
        "H3",
        "H5",
        "H6",
        "H7",
    }
    assert prereg["preserves_history"] == ["EXP-HF-H1-01"]


def test_h1_h4_v2_requires_real_independent_units_and_open_tasks() -> None:
    prereg = _load(PREREG)
    units = prereg["sampling_units"]
    assert units["Human_primary_unit"] == "independent_team_trace"
    assert units["Agent_primary_unit"] == "independent_agent_run"
    assert len(prereg["task_design"]["candidate_families"]) >= 4
    for family in prereg["task_design"]["candidate_families"].values():
        assert len(family["candidate_surfaces"]) >= 2
        assert len(family["conditions"]) == 2
    assert prereg["h4_measurement"]["outputs_are_a_profile_not_one_total_score"] is True


def test_h1_h4_v2_has_privacy_blinding_and_freeze_gates() -> None:
    prereg = _load(PREREG)
    assert "name" in prereg["target_population"]["prohibited_identifiers"]
    assert "central_server_with_HTTPS" in prereg["collection_system_requirements"]["deployment"]
    assert "three_role_specific_single_use_tokens" in prereg["collection_system_requirements"]["session"]
    assert prereg["rater_assignment"]["rater_sees_source_label"] is False
    assert len(prereg["freeze_and_stop_gates"]["before_any_formal_data"]) >= 8
    assert prereg["freeze_and_stop_gates"]["no_posthoc_repair_of_formal_data"] is True

