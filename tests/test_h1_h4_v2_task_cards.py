from __future__ import annotations

from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card

ROOT = Path(__file__).resolve().parents[1]
TASK_ROOT = ROOT / "human_validity" / "h1_h4_v2" / "tasks"
CARD_PATHS = sorted(TASK_ROOT.glob("*/task_card.yaml"))


def _load(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _conditions(card: dict, surface: dict) -> dict:
    value = surface.get("conditions", card.get("conditions"))
    assert isinstance(value, dict)
    return value


def test_index_registers_four_families_and_eight_unique_surfaces() -> None:
    index = _load(TASK_ROOT / "INDEX.yaml")
    assert index["formal_data_collection_allowed"] is False
    assert index["visible_output_mode"] == "natural_language"
    assert len(index["cards"]) == 4
    surface_ids = [
        surface_id for card in index["cards"] for surface_id in card["surfaces"]
    ]
    assert len(surface_ids) == 8
    assert len(surface_ids) == len(set(surface_ids))
    assert len(CARD_PATHS) == 4

    indexed_families = []
    indexed_paths = []
    for entry in index["cards"]:
        path = TASK_ROOT / entry["path"]
        card = _load(path)
        indexed_paths.append(path.resolve())
        indexed_families.append(card["family_id"])
        assert card["family_id"] == entry["family_id"]
        assert [surface["surface_id"] for surface in card["surfaces"]] == entry[
            "surfaces"
        ]
    assert len(indexed_families) == len(set(indexed_families)) == 4
    assert set(indexed_paths) == {path.resolve() for path in CARD_PATHS}


def test_each_candidate_passes_base_task_card_schema() -> None:
    for path in CARD_PATHS:
        result = validate_task_card(_load(path))
        assert result.valid, (path, result.errors)
        assert not result.warnings, (path, result.warnings)


def test_each_card_is_non_code_three_role_two_condition_design() -> None:
    all_surface_ids = []
    registered_manipulations = []
    for path in CARD_PATHS:
        card = _load(path)
        assert card["task_family"] == "T3"
        assert card["target_axis"] == "both"
        assert card["formal_data_collection_allowed"] is False
        assert card["non_code_task"] is True
        assert len(card["roles"]) == 3
        role_ids = [role["role_id"] for role in card["roles"]]
        assert len(role_ids) == len(set(role_ids))
        assert all(role["sees"] and role["prohibited"] for role in card["roles"])
        assert len(card["surfaces"]) == 2
        assert card["only_change"]
        registered_manipulations.append(card["only_change"])
        assert set(card["forbidden_primary_outputs"]) == {
            "source_code",
            "raw_JSON",
        }
        visible = " ".join(card["primary_visible_outputs"]).lower()
        assert "source_code" not in visible
        assert "raw_json" not in visible
        for surface in card["surfaces"]:
            all_surface_ids.append(surface["surface_id"])
            assert set(_conditions(card, surface)) == {"A", "B"}
    assert len(all_surface_ids) == len(set(all_surface_ids)) == 8
    assert len(registered_manipulations) == len(set(registered_manipulations)) == 4


def test_function_h1_and_h4_outputs_are_separate() -> None:
    for path in CARD_PATHS:
        card = _load(path)
        assert set(card["primary_metric"]) == {"functional", "H1", "H4"}
        assert card["oracle"]["functional_only"] is True
        assert card["human_reference"].endswith("-v2-draft")
        assert card["human_reference_design"]["current_status"] == "not_collected"
        assert "source_kind" in card["h1_display"]["exclude"]
        assert "functional_score" in card["h1_display"]["exclude"]
        assert len(card["required_events"]) >= 6
        assert card["h4_opportunities"]


def test_information_leak_and_cross_condition_contamination_are_invalid() -> None:
    for path in CARD_PATHS:
        rules = " ".join(_load(path)["contamination_rules"])
        assert "same_surface_other_condition" in rules
        assert "Human_and_Agent_receive_different" in rules


def test_joint_prioritization_remains_blocked_on_coordination_dependency() -> None:
    card = _load(TASK_ROOT / "prioritization" / "task_card.yaml")
    assert card["status"] == "draft_blocked_by_coordination_dependency"
    assert (
        card["dependency"]["requirement"]
        == "C1_or_equivalent_coordination_path_must_pass_rule_calibration"
    )
    assert "legitimate_no_consensus" in card["workflow"]["termination"]
