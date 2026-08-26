"""Load and validate registered T6 population tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

MODES = ("individual", "cohort", "fast_forward")
TRACKS = ("continuous", "checkpoint_resume")


def load_tasks() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("tasks.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tasks = list(payload.get("tasks") or [])
    for task in tasks:
        values = dict(task.get("subgroup_values") or {})
        drift = dict(task.get("subgroup_drift") or {})
        if not values or set(values) != set(drift):
            raise ValueError(f"subgroup mismatch for {task.get('id')}")
        if any(not group_values for group_values in values.values()):
            raise ValueError(f"empty subgroup for {task.get('id')}")
        if int(task.get("days") or 0) <= 1:
            raise ValueError(f"invalid duration for {task.get('id')}")
        if not 0 <= float(task.get("persistence")) <= 1:
            raise ValueError(f"invalid persistence for {task.get('id')}")
    return tasks


def members_for(task: dict[str, Any]) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for subgroup, values in task["subgroup_values"].items():
        for index, value in enumerate(values, start=1):
            members.append(
                {
                    "agent_id": f"{task['id']}:{subgroup}:{index}",
                    "subgroup": str(subgroup),
                    "value": float(value),
                }
            )
    return members
