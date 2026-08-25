"""CAL-GM-C1-PRIORITY-01 tasks. Not C1-01 / COMP / REPAIR / C1-02 items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("c1prio_autoclave_001", "c1prio_darkroom_001", "c1prio_mass_spec_001")
VARIANTS = ("control", "intervention")
BANNED = (
    "c1_charge_slot_001",
    "c1_device_book_001",
    "c1_dock_window_001",
    "c1comp_initial_conflict_001",
    "c1comp_final_free_001",
    "c1comp_reallocate_001",
    "c1repair_initial_conflict_001",
    "c1repair_final_free_001",
    "c1repair_reallocate_001",
    "c1_02_optics_table_001",
    "c1_02_greenhouse_001",
    "c1_02_cold_store_001",
    "c1_02_uav_pad_001",
    "charger_A",
    "mill_01",
    "dock_1",
    "pump_hose",
    "radio_desk",
    "ferry_berth",
    "optics_table",
    "greenhouse_valve",
    "cold_store",
    "uav_pad",
    "h8",
    "k1",
    "w08",
    "g14",
    "c14",
    "u08",
)


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["oracle_path"] = ROOT / "oracle" / f"{task_id}.json"
    payload["oracle"] = json.loads(payload["oracle_path"].read_text(encoding="utf-8"))
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def initial_assignments(task: dict[str, Any], variant: str) -> dict[str, str]:
    return {
        "agent_a": str(task["agent_a"]["preferred"]),
        "agent_b": str(task["agent_b"][variant]["preferred"]),
    }


def feasible_map(task: dict[str, Any], variant: str) -> dict[str, list[str]]:
    return {
        "agent_a": list(task["agent_a"]["feasible"]),
        "agent_b": list(task["agent_b"][variant]["feasible"]),
    }


def solve(task: dict[str, Any], variant: str) -> dict[str, str]:
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    blocks = {"agent_a": dict(task["agent_a"]), "agent_b": dict(task["agent_b"][variant])}
    for agent_id in task["priority"]:
        private = blocks[agent_id]
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


def oracle_plan(task: dict[str, Any], variant: str) -> dict[str, str]:
    return dict(task["oracle"][variant]["assignments"])


def trap_plan(task: dict[str, Any]) -> dict[str, str]:
    slots = list(task["slots"])
    return {"agent_a": slots[1], "agent_b": slots[2]}
