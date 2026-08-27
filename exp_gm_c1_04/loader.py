"""Fresh C1-04 task surfaces and deterministic reference solutions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = (
    "c1_04_telescope_mount_001",
    "c1_04_vaccine_transfer_001",
    "c1_04_acoustic_booth_001",
)
VARIANTS = ("control", "intervention")
TRACK = "full"
RULE_ID = "priority_preferred_then_feasible_order"


def load_task(task_id: str) -> dict[str, Any]:
    task = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    task["oracle"] = json.loads((ROOT / "oracle" / f"{task_id}.json").read_text(encoding="utf-8"))
    return task


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def private_for(task: dict[str, Any], agent_id: str, variant: str) -> dict[str, Any]:
    block = task[agent_id]
    variant_block = block[variant]
    return {
        "agent_id": agent_id,
        "resource_id": task["resource_id"],
        "feasible": list(variant_block["feasible"]),
        "preferred": str(variant_block["preferred"]),
    }


def solve(priority: list[str], reports: dict[str, dict[str, Any]]) -> dict[str, str]:
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    for agent_id in priority:
        report = reports[agent_id]
        feasible = list(report["feasible"])
        preferred = str(report["preferred"])
        slot = preferred if preferred in feasible and preferred not in occupied else next(
            (candidate for candidate in feasible if candidate not in occupied), ""
        )
        assignments[agent_id] = slot
        occupied.add(slot)
    return assignments


def final_solution(task: dict[str, Any], reports: dict[str, dict[str, Any]]) -> dict[str, str]:
    protected = task["protection"]
    agent_id = str(protected["agent_id"])
    protected_slot = str(protected["slot"])
    other = "agent_b" if agent_id == "agent_a" else "agent_a"
    other_slot = next(
        candidate for candidate in reports[other]["feasible"] if candidate != protected_slot
    )
    return {agent_id: protected_slot, other: other_slot}
