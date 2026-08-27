"""Contract tests for expanded sealed T5-v3 surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from benchmark_core.task_card import validate_task_card
from exp_gm_t5_01.loader import load_tasks as load_v1_tasks
from exp_gm_t5_02.loader import load_tasks as load_v2_tasks
from holdout_t5_v3.loader import load_tasks as load_first_holdout
from holdout_t5_v3_expanded.loader import TASK_IDS, load_tasks


def _surfaces(tasks: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {
        "task_ids": {str(task["id"]) for task in tasks},
        "policy_ids": {str(task["policy_id"]) for task in tasks},
        "channels": {str(task["policy_signal"]["channel"]) for task in tasks},
        "actions": {str(task["target_action"]) for task in tasks},
        "agent_ids": {
            str(resident["agent_id"])
            for task in tasks
            for resident in task["residents"]
        },
        "groups": {
            str(resident["group"]) for task in tasks for resident in task["residents"]
        },
        "state_fields": {
            str(field)
            for task in tasks
            for resident in task["residents"]
            for field in resident["state"]
        },
    }


def test_expanded_holdout_task_card_and_order_are_valid() -> None:
    path = Path(__file__).parents[1] / "holdout_t5_v3_expanded" / "task_card.yaml"
    result = validate_task_card(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert result.valid, result.errors
    assert tuple(str(task["id"]) for task in load_tasks()) == TASK_IDS


def test_expanded_holdout_surfaces_are_disjoint_from_all_prior_t5_tasks() -> None:
    expanded = load_tasks()
    prior = [*load_v1_tasks(), *load_v2_tasks(), *load_first_holdout()]
    expanded_surfaces = _surfaces(expanded)
    prior_surfaces = _surfaces(prior)

    for surface_name in expanded_surfaces:
        assert expanded_surfaces[surface_name].isdisjoint(
            prior_surfaces[surface_name]
        ), surface_name
    assert all(
        sum(
            resident["group"] in set(task["target_groups"])
            for resident in task["residents"]
        )
        == 2
        for task in expanded
    )
