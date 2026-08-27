"""Load the frozen T5-v2 task surfaces for the isolated v3 protocol repair."""

from __future__ import annotations

from typing import Any

from exp_gm_t5_02.loader import load_tasks as load_v2_tasks

TASK_IDS = (
    "t5v2_water_restriction_001",
    "t5v2_heat_activity_001",
    "t5v2_organics_rule_001",
)


def load_tasks() -> list[dict[str, Any]]:
    tasks = load_v2_tasks()
    by_id = {str(task["id"]): task for task in tasks}
    if set(by_id) != set(TASK_IDS):
        raise ValueError("T5-v3 requires the exact frozen T5-v2 task set")
    return [by_id[task_id] for task_id in TASK_IDS]


__all__ = ["TASK_IDS", "load_tasks"]
