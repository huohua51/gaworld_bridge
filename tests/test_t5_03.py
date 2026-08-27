"""Contract tests for the T5-v3 resident eligibility-scope protocol."""

from __future__ import annotations

from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t5_03.loader import TASK_IDS, load_tasks
from exp_gm_t5_03.semantics import policy_signal, resident_directive


def test_t5_v3_task_card_and_frozen_task_order_are_valid() -> None:
    path = Path(__file__).parents[1] / "exp_gm_t5_03" / "task_card.yaml"
    result = validate_task_card(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert result.valid, result.errors
    assert tuple(str(task["id"]) for task in load_tasks()) == TASK_IDS


def test_t5_v3_separates_global_policy_action_from_resident_authority() -> None:
    task = load_tasks()[0]
    signal = policy_signal(task, "binding")

    assert signal["policy_action"] == task["target_action"]
    assert "required_action" not in signal
    assert resident_directive(task, "absence", None) == {
        "target_match": False,
        "authorized": False,
        "action": "keep_current",
        "authority": "sole_action_authority",
    }
    assert resident_directive(task, "binding", {"ok": True, "eligible": True})[
        "action"
    ] == task["target_action"]
    assert resident_directive(task, "binding", {"ok": True, "eligible": False})[
        "action"
    ] == "keep_current"
    assert resident_directive(
        task, "nonbinding", {"ok": True, "eligible": True}
    ) == {
        "target_match": True,
        "authorized": False,
        "action": "keep_current",
        "authority": "sole_action_authority",
    }
