from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t4_01.run_matrix import run_rule_matrix


def test_t4_task_card_uses_versioned_schema() -> None:
    path = Path(__file__).resolve().parents[1] / "exp_gm_t4_01" / "task_card.yaml"
    card = yaml.safe_load(path.read_text(encoding="utf-8"))

    result = validate_task_card(card)

    assert result.valid is True


def test_t4_rule_matrix_has_registered_positive_and_negative_controls(
    tmp_path: Path,
) -> None:
    cells, report = run_rule_matrix(tmp_path / "t4")

    assert len(cells) == 18
    assert report["gate"] == "rule_calibration_pass"
    assert report["coverage"] == 1.0
    assert report["FullPassByVariant"]["full"] == {"control": 1.0, "intervention": 1.0}
    assert report["FullPassByVariant"]["remove_bridge"] == {
        "control": 1.0,
        "intervention": 0.0,
    }
    assert report["FullPassByVariant"]["drop_bridge"] == {
        "control": 1.0,
        "intervention": 0.0,
    }
    assert report["CommunicationValueRemoveBridge"] == 1.0
    assert report["CommunicationValueDropBridge"] == 1.0

    critical = [
        criterion
        for cell in cells
        for criterion in cell["criteria"]
        if criterion["critical"] and criterion["evaluable"]
    ]
    assert critical
    assert all(criterion["evidence_ids"] for criterion in critical)
    assert all(
        next(gate for gate in cell["gates"] if gate["gate_id"] == "eval_mode_on")[
            "passed"
        ]
        for cell in cells
    )
