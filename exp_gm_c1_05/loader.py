"""Fresh C1-05 task surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = (
    "c1_05_satellite_dish_001",
    "c1_05_cleanroom_airlock_001",
    "c1_05_lidar_tunnel_001",
)
VARIANTS = ("control", "intervention")
RULE_ID = "authoritative_protection_then_feasible_order"


def load_task(task_id: str) -> dict[str, Any]:
    task = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    task["oracle"] = json.loads((ROOT / "oracle" / f"{task_id}.json").read_text(encoding="utf-8"))
    return task


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def private_for(task: dict[str, Any], agent_id: str, variant: str) -> dict[str, Any]:
    block = task[agent_id][variant]
    return {
        "agent_id": agent_id,
        "resource_id": task["resource_id"],
        "feasible": list(block["feasible"]),
        "preferred": str(block["preferred"]),
    }


def solve(priority: list[str], reports: dict[str, dict[str, Any]]) -> dict[str, str]:
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    for agent_id in priority:
        report = reports[agent_id]
        feasible = list(report["feasible"])
        preferred = str(report["preferred"])
        slot = preferred if preferred in feasible and preferred not in occupied else next(
            candidate for candidate in feasible if candidate not in occupied
        )
        assignments[agent_id] = slot
        occupied.add(slot)
    return assignments
