"""Load and validate T4-v2 registered-transport tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

TRACKS = ("full", "remove_bridge", "drop_bridge")
VARIANTS = ("control", "intervention")


def load_tasks() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("tasks.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tasks = list(payload.get("tasks") or [])
    if not tasks:
        raise ValueError("T4-v2 requires at least one registered task")
    seen: set[str] = set()
    for task in tasks:
        task_id = str(task.get("id") or "")
        if not task_id or task_id in seen:
            raise ValueError(f"invalid or duplicate task id: {task_id}")
        seen.add(task_id)
        route = [str(node) for node in task.get("path") or []]
        bridge = [str(node) for node in task.get("bridge") or []]
        if len(route) != 4 or len(bridge) != 2:
            raise ValueError(f"invalid topology for {task_id}")
        pairs = [route[index : index + 2] for index in range(len(route) - 1)]
        if bridge not in pairs:
            raise ValueError(f"bridge is not on registered path for {task_id}")
        if task.get("source") != route[0] or task.get("target") != route[-1]:
            raise ValueError(f"source/target mismatch for {task_id}")
        if task.get("message_class") != "registered_status_update":
            raise ValueError(f"invalid message class for {task_id}")
        control = dict(task.get("control_payload") or {})
        intervention = dict(task.get("intervention_payload") or {})
        if control.get("action_required") is not False:
            raise ValueError(f"control must be no-action for {task_id}")
        if control.get("target_action") != "keep_current":
            raise ValueError(f"control action must be keep_current for {task_id}")
        if intervention.get("action_required") is not True:
            raise ValueError(f"intervention must require action for {task_id}")
        if intervention.get("target_action") in {None, "", "keep_current"}:
            raise ValueError(f"intervention action is invalid for {task_id}")
    return tasks


def payload_for(task: dict[str, Any], variant: str) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    return dict(task[f"{variant}_payload"])
