"""Load and validate expanded sealed T5-v3 tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

TASK_IDS = (
    "t5ho2_cold_chain_001",
    "t5ho2_smoke_shelter_001",
    "t5ho2_nursery_quarantine_001",
    "t5ho2_bridge_weight_001",
)


def load_tasks() -> list[dict[str, Any]]:
    payload = (
        yaml.safe_load(
            Path(__file__).with_name("tasks.yaml").read_text(encoding="utf-8")
        )
        or {}
    )
    tasks = list(payload.get("tasks") or [])
    if tuple(str(task.get("id") or "") for task in tasks) != TASK_IDS:
        raise ValueError("expanded sealed T5-v3 task order or IDs changed")
    for task in tasks:
        residents = list(task.get("residents") or [])
        resident_ids = [str(item.get("agent_id") or "") for item in residents]
        targets = {str(item) for item in task.get("target_groups") or []}
        target_count = sum(
            str(item.get("group") or "") in targets for item in residents
        )
        effects = dict(task.get("action_effects") or {})
        if len(residents) != 4 or len(set(resident_ids)) != 4:
            raise ValueError(f"invalid expanded sealed population: {task['id']}")
        if target_count != 2:
            raise ValueError(
                f"expanded sealed task must have exactly two targets: {task['id']}"
            )
        if "keep_current" not in effects or task.get("target_action") not in effects:
            raise ValueError(f"invalid expanded sealed actions: {task['id']}")
        if int(task.get("effective_step") or -1) < 0:
            raise ValueError(f"invalid expanded sealed effective step: {task['id']}")
    return tasks


__all__ = ["TASK_IDS", "load_tasks"]
