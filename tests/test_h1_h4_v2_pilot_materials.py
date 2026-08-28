from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
H1H4_ROOT = ROOT / "human_validity" / "h1_h4_v2"
TASK_ROOT = H1H4_ROOT / "tasks"


def _load(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_each_indexed_task_has_role_specific_instructions_and_scoring() -> None:
    index = _load(TASK_ROOT / "INDEX.yaml")
    for relative_path in index["shared_materials"].values():
        assert (TASK_ROOT / relative_path).resolve().is_file()
    for entry in index["cards"]:
        task_card = _load(TASK_ROOT / entry["path"])
        instructions = _load(TASK_ROOT / entry["participant_instructions"])
        scoring = _load(TASK_ROOT / entry["scoring"])

        assert instructions["task_id"] == scoring["task_id"] == task_card["task_id"]
        assert instructions["formal_data_collection_allowed"] is False
        assert scoring["formal_data_collection_allowed"] is False
        assert instructions["condition_label_visible"] is False
        assert instructions["source_label_visible"] is False
        assert instructions["file_is_server_side_only"] is True
        never_send = set(instructions["render_contract"]["never_send_to_client"])
        assert {"other_role_cards", "hidden_bindings", "condition_code", "source_kind"} <= never_send
        assert "pre_task_comprehension.items.expected_concept" in never_send

        task_roles = {role["role_id"] for role in task_card["roles"]}
        instruction_roles = {role["role_id"] for role in instructions["role_cards"]}
        assert instruction_roles == task_roles
        for role in instructions["role_cards"]:
            visible = set(role["visible_bindings"])
            hidden = set(role["hidden_bindings"])
            assert visible.isdisjoint(hidden)
            assert {"condition_code", "source_kind"} <= hidden
            assert role["participant_text"]
            assert role["available_actions"]
            assert role["completion_check"]

        comprehension = instructions["pre_task_comprehension"]
        assert len(comprehension["items"]) >= 2
        assert comprehension["attempts_before_facilitator_review"] == 2


def test_scoring_keeps_function_h1_and_h4_separate() -> None:
    for path in sorted(TASK_ROOT.glob("*/scoring.yaml")):
        scoring = _load(path)
        assert scoring["R0_validity"]["invalid_if"]
        assert scoring["R0_validity"]["retain_invalid_count_and_reason"] is True
        assert scoring["functional_oracle"]["metrics"]
        oracle = scoring["functional_oracle"]
        assert oracle.get("binary_pass_rule") or oracle.get("valid_terminal_states")
        assert scoring["functional_oracle"]["H_score_effect"].startswith("none_")
        assert scoring["H4_metrics"]
        assert scoring["H1_handling"]["scored_here"] is False
        assert scoring["rule_calibration_cases"]["positive_control"]
        assert scoring["rule_calibration_cases"]["negative_controls"]


def test_h4_codebook_requires_opportunities_blinding_and_double_coding() -> None:
    codebook = _load(H1H4_ROOT / "H4_CODEBOOK.yaml")
    assert codebook["formal_data_collection_allowed"] is False
    assert codebook["source_blinded_coding_required"] is True
    assert codebook["opportunity_rules"]["zero_denominator"] == "report_NA_not_zero"
    assert codebook["double_coding"]["independent_coders"] == 2
    assert codebook["reporting"]["no_cross_metric_total"] is True


def test_pilot_plan_is_not_run_and_has_no_priority_in_wave_1() -> None:
    plan = _load(H1H4_ROOT / "PILOT_PLAN.yaml")
    assert plan["status"] == "planned_not_run"
    assert plan["formal_data_collection_allowed"] is False
    assert plan["raw_data_in_public_git_allowed"] is False
    assert plan["wave_1"]["people"] == 12
    assert plan["wave_1"]["teams"] == 4
    assert plan["wave_2"]["people"] == 6
    assert plan["wave_2"]["status"] == "blocked_by_coordination_dependency"
    assert plan["participant_plan"]["teams_total_after_both_waves"] == 6
    assert plan["participant_plan"]["live_internal_pilot_people_total_after_both_waves"] == 18
    assert sum(wave["teams"] for wave in (plan["wave_1"], plan["wave_2"])) * 3 == 18

    wave_1_assignments = [
        assignment
        for team in plan["wave_1"]["assignments"]
        for assignment in team["order"]
    ]
    wave_2_assignments = [
        assignment
        for team in plan["wave_2"]["assignments"]
        for assignment in team["order"]
    ]
    assert len(wave_1_assignments) == plan["wave_1"]["planned_traces"]
    assert len(wave_2_assignments) == plan["wave_2"]["planned_traces"]
    assert all(not item["surface_id"].startswith("priority_") for item in wave_1_assignments)
    assert all(item["surface_id"].startswith("priority_") for item in wave_2_assignments)


def test_pilot_assignments_cover_all_surfaces_and_both_conditions_by_family() -> None:
    index = _load(TASK_ROOT / "INDEX.yaml")
    plan = _load(H1H4_ROOT / "PILOT_PLAN.yaml")
    surface_to_family = {
        surface: entry["family_id"]
        for entry in index["cards"]
        for surface in entry["surfaces"]
    }
    assignments = [
        assignment
        for wave in (plan["wave_1"], plan["wave_2"])
        for team in wave["assignments"]
        for assignment in team["order"]
    ]
    assert {item["surface_id"] for item in assignments} == set(surface_to_family)
    for family_id in set(surface_to_family.values()):
        family_conditions = {
            item["condition"]
            for item in assignments
            if surface_to_family[item["surface_id"]] == family_id
        }
        assert family_conditions == {"A", "B"}

    for wave in (plan["wave_1"], plan["wave_2"]):
        for team in wave["assignments"]:
            team_surfaces = [item["surface_id"] for item in team["order"]]
            assert len(team_surfaces) == len(set(team_surfaces))
