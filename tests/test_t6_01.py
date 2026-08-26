"""Rule calibration for EXP-GM-T6-01."""

from __future__ import annotations

from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t6_01.loader import load_tasks
from exp_gm_t6_01.loop import run_cell
from exp_gm_t6_01.run_matrix import _eval_evidence, run_rule_matrix
from exp_gm_t6_01.scorer import score_cell


def test_t6_task_card_uses_versioned_contract() -> None:
    path = Path(__file__).parents[1] / "exp_gm_t6_01" / "task_card.yaml"
    result = validate_task_card(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert result.valid, result.errors


def test_t6_rule_matrix_preserves_registered_moments_and_resume(tmp_path: Path) -> None:
    cells, report = run_rule_matrix(tmp_path / "t6")

    assert len(cells) == 18
    assert report["gate"] == "rule_calibration_pass"
    assert report["coverage"] == 1.0
    assert report["FullPassByMode"] == {
        "individual": 1.0,
        "cohort": 1.0,
        "fast_forward": 1.0,
    }
    assert report["FullPassByTrack"] == {
        "continuous": 1.0,
        "checkpoint_resume": 1.0,
    }
    assert max(report["MaxRegisteredDistributionGap"].values()) <= 1e-9
    ratios = report["OperationCostRatioToIndividual"]
    assert ratios["fast_forward"] < ratios["cohort"] < 1.0
    assert all(cell["ranking_eligible"] is False for cell in cells)
    assert all(
        criterion["evidence_ids"]
        for cell in cells
        for criterion in cell["criteria"]
        if criterion["critical"] and criterion["evaluable"]
    )


def test_t6_scorer_uses_persisted_completion_summary(tmp_path: Path) -> None:
    task = load_tasks()[0]
    loop = run_cell(task, "cohort", "continuous", tmp_path / "trace-source")
    loop["summary"]["overall_mean"] += 100

    cell = score_cell(
        task=task,
        mode="cohort",
        track="continuous",
        seed=0,
        loop=loop,
        eval_mode_evidence=_eval_evidence(),
    )

    assert cell["measurement_valid"] is True
    assert cell["full_pass"] == 1
    assert cell["extra"]["max_distribution_error"] <= 1e-9
