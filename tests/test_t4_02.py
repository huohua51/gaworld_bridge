"""Calibration tests for the independent T4-v2 experiment."""

from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t4_01.loader import load_tasks as load_v1_tasks
from exp_gm_t4_02.loader import load_tasks
from exp_gm_t4_02.run_matrix import run_rule_matrix


def test_t4_v2_task_card_and_tasks_are_independent() -> None:
    root = Path(__file__).resolve().parents[1]
    card = yaml.safe_load(
        (root / "exp_gm_t4_02" / "task_card.yaml").read_text(encoding="utf-8")
    )

    result = validate_task_card(card)
    v1_ids = {str(task["id"]) for task in load_v1_tasks()}
    v2_tasks = load_tasks()

    assert result.valid is True
    assert len(v2_tasks) == 3
    assert not v1_ids & {str(task["id"]) for task in v2_tasks}
    assert all(task["message_class"] == "registered_status_update" for task in v2_tasks)
    assert all(
        task["control_payload"]["action_required"] is False
        and task["control_payload"]["target_action"] == "keep_current"
        and task["intervention_payload"]["action_required"] is True
        for task in v2_tasks
    )


def test_t4_v2_rule_matrix_calibrates_transport_and_bridge_controls(
    tmp_path: Path,
) -> None:
    cells, report = run_rule_matrix(tmp_path / "t4-v2")

    assert len(cells) == 18
    assert report["gate"] == "rule_calibration_pass"
    assert report["coverage"] == 1.0
    assert report["FullPassByVariant"]["full"] == {
        "control": 1.0,
        "intervention": 1.0,
    }
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

    full_cells = [
        cell
        for cell in cells
        if cell["extra"]["run_context"]["track"] == "full"
    ]
    assert full_cells
    for cell in full_cells:
        criteria = {item["criterion_id"]: item for item in cell["criteria"]}
        assert criteria["target_update_accepted"]["critical"] is True
        assert criteria["target_update_accepted"]["passed"] is True
        assert criteria["complete_propagation_path"]["critical"] is True
        assert criteria["complete_propagation_path"]["passed"] is True

    critical = [
        criterion
        for cell in cells
        for criterion in cell["criteria"]
        if criterion["critical"] and criterion["evaluable"]
    ]
    assert critical
    assert all(criterion["evidence_ids"] for criterion in critical)
