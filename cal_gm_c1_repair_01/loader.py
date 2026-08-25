from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("c1repair_initial_conflict_001", "c1repair_final_free_001", "c1repair_reallocate_001")
VARIANTS = ("control", "intervention")
BANNED = (
    "c1_charge_slot_001",
    "c1_device_book_001",
    "c1_dock_window_001",
    "c1comp_initial_conflict_001",
    "c1comp_final_free_001",
    "c1comp_reallocate_001",
    "charger_A",
    "mill_01",
    "dock_1",
    "locker_bay",
    "lab_bench",
    "van_bay",
    "bay-1",
    "bench-1",
    "h8",
    "PARKING",
    "FREE_SHIP",
)


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["oracle_path"] = ROOT / "oracle" / f"{task_id}.json"
    payload["oracle"] = json.loads(payload["oracle_path"].read_text(encoding="utf-8"))
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def initial_conflict(task: dict[str, Any], variant: str) -> bool:
    a = task["agent_a"]
    b = task["agent_b"][variant]
    return a["resource"] == b["resource"] and a["slot"] == b["slot"]


def given_final(task: dict[str, Any], variant: str) -> dict[str, str]:
    return dict(task["final"][variant])


def initial_assignments(task: dict[str, Any], variant: str) -> dict[str, str]:
    a = task["agent_a"]
    b = task["agent_b"][variant]
    return {"agent_a": str(a["preferred"]), "agent_b": str(b["preferred"])}


def feasible_map(task: dict[str, Any], variant: str) -> dict[str, list[str]]:
    a = task["agent_a"]
    b = task["agent_b"][variant]
    return {"agent_a": list(a["feasible"]), "agent_b": list(b["feasible"])}


def solve_reallocate(task: dict[str, Any], variant: str) -> dict[str, str]:
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    a = dict(task["agent_a"])
    b = dict(task["agent_b"][variant])
    for agent_id, private in (("agent_a", a), ("agent_b", b)):
        preferred = private["preferred"]
        feasible = list(private["feasible"])
        if preferred in feasible and preferred not in occupied:
            slot = preferred
        else:
            slot = next((item for item in feasible if item not in occupied), "")
        assignments[agent_id] = slot
        if slot:
            occupied.add(slot)
    return assignments


def oracle_value(task: dict[str, Any], variant: str) -> Any:
    component = task["component"]
    if component in {"A", "B"}:
        return bool(task["oracle"][variant])
    return dict(task["oracle"][variant])
