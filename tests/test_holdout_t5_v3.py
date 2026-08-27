"""Contract tests for the fresh-surface T5-v3 sealed holdout."""

from __future__ import annotations

from pathlib import Path

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t5_01.loader import load_tasks as load_v1_tasks
from exp_gm_t5_02.loader import load_tasks as load_v2_tasks
from holdout_t5_v3.loader import TASK_IDS, load_tasks


def test_t5_v3_holdout_task_card_and_order_are_valid() -> None:
    path = Path(__file__).parents[1] / "holdout_t5_v3" / "task_card.yaml"
    result = validate_task_card(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert result.valid, result.errors
    assert tuple(str(task["id"]) for task in load_tasks()) == TASK_IDS


def test_t5_v3_holdout_surfaces_are_disjoint_from_development_tasks() -> None:
    holdout = load_tasks()
    development = [*load_v1_tasks(), *load_v2_tasks()]

    assert {task["id"] for task in holdout}.isdisjoint(
        {task["id"] for task in development}
    )
    assert {task["target_action"] for task in holdout}.isdisjoint(
        {task["target_action"] for task in development}
    )
    assert {
        resident["agent_id"] for task in holdout for resident in task["residents"]
    }.isdisjoint(
        {
            resident["agent_id"]
            for task in development
            for resident in task["residents"]
        }
    )
    assert all(
        sum(
            resident["group"] in set(task["target_groups"])
            for resident in task["residents"]
        )
        == 2
        for task in holdout
    )
