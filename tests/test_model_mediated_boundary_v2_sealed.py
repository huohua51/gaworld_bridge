from __future__ import annotations

import json

from cross_platform.model_mediated_boundary_v2_sealed.common import (
    CONDITIONS,
    PLATFORMS,
    build_prompt,
    load_cards,
)
from cross_platform.model_mediated_boundary_v2_sealed.run import (
    fixture_client,
    run_calibration,
    run_formal,
)


def test_sealed_fixture_has_disaggregated_pressure_matrix(tmp_path):
    calibration = run_calibration(tmp_path / "calibration", fixture_client())
    assert calibration["gate"] == "pass"
    assert calibration["strict_valid"] == 3
    assert calibration["full_expected"] == 3

    out = tmp_path / "formal"
    manifest = run_formal(out, fixture_client(), fixture=True)
    cells = json.loads((out / "cell_table.json").read_text(encoding="utf-8"))
    assert manifest["new_model_calls"] == 0
    assert manifest["ranking_eligible"] is False
    assert len(cells) == 24
    assert all(cell["action_correct"] for cell in cells)
    assert all(cell["authority_binding_correct"] for cell in cells)
    assert all(cell["owner_correct"] for cell in cells)
    assert manifest["platform_summary"]["GAWorld"]["full_policy_pass"] == 8
    assert manifest["platform_summary"]["YuLan-OneSim"]["full_policy_pass"] == 8
    assert manifest["platform_summary"]["AgentSociety2"]["full_policy_pass"] == 8
    assert manifest["platform_summary"]["GAWorld"]["pressure_pairs_full_pass"] == 4
    assert manifest["platform_summary"]["AgentSociety2"]["defense_in_depth_safe"] == 6


def test_sealed_prompts_do_not_expose_or_position_encode_answers():
    cards = load_cards()
    prompts = {
        build_prompt(platform=platform, task=task, condition=condition)
        for platform in PLATFORMS
        for task in cards["formal_tasks"]
        for condition in CONDITIONS
    }
    assert len(prompts) == 24
    assert all('\n"expected"' not in prompt for prompt in prompts)

    correct_choice_positions = {
        next(
            index
            for index, choice in enumerate(task["choices"])
            if choice["choice_id"] == task["expected"]["choice_id"]
        )
        for task in cards["formal_tasks"]
    }
    governing_record_positions = {
        next(
            index
            for index, record in enumerate(task["records"])
            if record["record_id"] == task["expected"]["governing_record_id"]
        )
        for task in cards["formal_tasks"]
    }
    assert correct_choice_positions == {0, 1}
    assert governing_record_positions == {0, 1, 2}
