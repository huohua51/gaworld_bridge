"""Load EXP-GM-OA-01 tasks and frozen oracles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("appointment_update", "resource_threshold", "responsibility_update")
PROTOCOLS = ("legacy_direct", "need_change_gate")
VARIANTS = ("control", "intervention")
NONE = "NONE"


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected mapping in {path}")
    return payload


def load_task(task_id: str) -> dict[str, Any]:
    task = _read_yaml(ROOT / "tasks" / f"{task_id}.yaml")
    oracle = _read_yaml(ROOT / "oracle" / f"{task_id}.yaml")
    if task.get("id") != task_id or oracle.get("task_id") != task_id:
        raise ValueError(f"task/oracle id mismatch: {task_id}")
    task["oracle"] = {
        "control": dict(oracle["control"]),
        "intervention": dict(oracle["intervention"]),
    }
    return task


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def event_id_for(task_id: str, variant: str) -> str:
    return f"event-{task_id}-{variant}"


def registered_plan(task: dict[str, Any]) -> dict[str, Any]:
    task_id = task["id"]
    if task_id == "appointment_update":
        return {"appointment_slot": task["plan_time"]}
    if task_id == "resource_threshold":
        return {"stock": task["control"]["stock"], "min_need": task["min_need"], "purchase_qty": 0}
    if task_id == "responsibility_update":
        return {"assignee_id": task["original_assignee"]}
    raise KeyError(task_id)


def current_state(task: dict[str, Any], variant: str) -> dict[str, Any]:
    block = dict(task[variant])
    description = block.pop("description")
    state: dict[str, Any] = {
        "task_id": task["id"],
        "title": task["title"],
        "state_key": task["state_key"],
        "registered_target": task["target"],
        "rule": task["rule"].strip(),
        "description": description,
        **block,
    }
    if task["id"] == "appointment_update":
        state.update(
            {
                "plan_time": task["plan_time"],
                "busy_times": list(task["busy_times"]),
                "alternate_time": task["alternate_time"],
            }
        )
    elif task["id"] == "resource_threshold":
        state["min_need"] = task["min_need"]
    elif task["id"] == "responsibility_update":
        state.update(
            {
                "original_assignee": task["original_assignee"],
                "backup_assignee": task["backup_assignee"],
            }
        )
    return state


def build_notice(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return {
        "event_id": event_id_for(task["id"], variant),
        "variant_is_hidden": True,
        "current_state": current_state(task, variant),
    }


def oracle_of(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return dict(task["oracle"][variant])
