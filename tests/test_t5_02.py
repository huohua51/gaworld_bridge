"""Rule and contract calibration for independent EXP-GM-T5-02."""

from __future__ import annotations

from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t5_01.loader import load_tasks as load_v1_tasks
from exp_gm_t5_02.loader import load_tasks
from exp_gm_t5_02.run_matrix import run_rule_matrix


def test_t5_v2_task_card_and_tasks_are_independent_from_v1() -> None:
    root = Path(__file__).parents[1]
    path = root / "exp_gm_t5_02" / "task_card.yaml"
    result = validate_task_card(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert result.valid, result.errors
    assert {task["id"] for task in load_tasks()}.isdisjoint(
        {task["id"] for task in load_v1_tasks()}
    )


def test_t5_v2_rule_matrix_calibrates_three_explicit_semantics(
    tmp_path: Path,
) -> None:
    cells, report = run_rule_matrix(tmp_path / "t5-v2")

    assert len(cells) == 18
    assert report["gate"] == "rule_calibration_pass"
    assert report["ranking_eligible"] is False
    assert report["FullPassByPolicyState"]["full"] == {
        "absence": 1.0,
        "binding": 1.0,
        "nonbinding": 1.0,
    }
    assert report["BehaviorChangeRate"] == {
        "absence": 0.0,
        "binding": 0.5,
        "nonbinding": 0.0,
    }
    assert report["BindingMinusAbsence"] == 0.5
    assert report["BindingMinusNonbinding"] == 0.5
    assert report["NonbindingMinusAbsence"] == 0.0
    assert report["DisconnectedTreatmentCellsRejectedAtR0"] == 6
    assert all(cell["ranking_eligible"] is False for cell in cells)
