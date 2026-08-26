"""Rule calibration for EXP-GM-T5-01."""

from __future__ import annotations

from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t5_01.loader import load_tasks
from exp_gm_t5_01.loop import run_cell
from exp_gm_t5_01.run_matrix import _eval_evidence, run_rule_matrix
from exp_gm_t5_01.scorer import score_cell


def test_t5_task_card_uses_versioned_contract() -> None:
    path = Path(__file__).parents[1] / "exp_gm_t5_01" / "task_card.yaml"
    result = validate_task_card(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert result.valid, result.errors


def test_t5_rule_matrix_calibrates_policy_placebo_and_r0(tmp_path: Path) -> None:
    cells, report = run_rule_matrix(tmp_path / "t5")

    assert len(cells) == 18
    assert report["gate"] == "rule_calibration_pass"
    assert report["ranking_eligible"] is False
    assert report["FullPassByCondition"]["full"] == {
        "no_policy": 1.0,
        "real_policy": 1.0,
        "placebo_policy": 1.0,
    }
    assert report["TreatmentEffect"] == 0.5
    assert report["PlaceboEffect"] == 0.0
    assert report["DisconnectedTreatmentCellsRejectedAtR0"] == 6
    assert all(cell["ranking_eligible"] is False for cell in cells)
    assert all(
        next(gate for gate in cell["gates"] if gate["gate_id"] == "eval_mode_on")[
            "passed"
        ]
        for cell in cells
    )


def test_t5_scorer_rebuilds_actions_from_trace(tmp_path: Path) -> None:
    task = load_tasks()[0]
    loop = run_cell(task, "real_policy", "full", tmp_path / "trace-source")
    loop["residents"] = []
    loop["changed_agent_ids"] = []
    loop["behavior_change_rate"] = 0.0

    cell = score_cell(
        task=task,
        condition="real_policy",
        track="full",
        seed=0,
        loop=loop,
        eval_mode_evidence=_eval_evidence(),
    )

    assert cell["measurement_valid"] is True
    assert cell["full_pass"] == 1
    assert cell["extra"]["behavior_change_rate"] == 0.5
