"""C1-02 tasks. Not C1-01 / COMP-01 / REPAIR-01 items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("c1_02_optics_table_001", "c1_02_greenhouse_001", "c1_02_cold_store_001")
TRACKS = ("multi", "drop_revision", "drop_coordinator")
VARIANTS = ("control", "intervention")
RULE_TEXT = (
    "先给高优先级 Agent 分配其 preferred（须在其可行集内且空闲）；"
    "再给低优先级 Agent 按其可行集列表顺序选择第一个空闲时段。"
    "禁止把未出现在该 Agent 可行集中的时段分配给该 Agent。"
)
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
    "charger_A",
    "mill_01",
    "dock_1",
    "locker_bay",
    "lab_bench",
    "van_bay",
    "pump_hose",
    "radio_desk",
    "ferry_berth",
    "h8",
    "k1",
    "morning-1",
    "desk-n",
)


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["oracle_path"] = ROOT / "oracle" / f"{task_id}.json"
    payload["oracle"] = json.loads(payload["oracle_path"].read_text(encoding="utf-8"))
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def leak_tokens_for(task: dict[str, Any], variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return list(task.get("leak_tokens") or [])


def _pack_private(task: dict[str, Any], agent_id: str, block: dict[str, Any]) -> dict[str, Any]:
    feasible = list(block["feasible"])
    if agent_id == "agent_a":
        label = block.get("label") or task["agent_a"].get("label") or agent_id
    else:
        label = block.get("label") or task.get("agent_b", {}).get("label") or agent_id
    return {
        "agent_id": agent_id,
        "label": label,
        "resource_id": task["resource_id"],
        "feasible": feasible,
        "preferred": block["preferred"],
        "window_token": str(block.get("window_token") or ("a_window_v1" if agent_id == "agent_a" else "")),
        "window_key": "+".join(feasible),
        "priority": "high" if agent_id == "agent_a" else "low",
    }


def agent_private(task: dict[str, Any], agent_id: str, variant: str) -> dict[str, Any]:
    if agent_id == "agent_a":
        return _pack_private(task, agent_id, dict(task["agent_a"]))
    return _pack_private(task, agent_id, dict(task["agent_b"][variant]))


def agent_baseline(task: dict[str, Any], agent_id: str) -> dict[str, Any]:
    if agent_id == "agent_a":
        return agent_private(task, "agent_a", "control")
    return _pack_private(task, "agent_b", dict(task["agent_b"]["baseline"]))


def public_spec(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": task["resource_id"],
        "slots": list(task["slots"]),
        "priority": list(task["priority"]),
        "rule": task["rule"],
        "rule_text": RULE_TEXT,
    }


def preferred_conflict_from(a_pref: str, b_pref: str) -> bool:
    return str(a_pref) == str(b_pref)


def solve_from_privates(task: dict[str, Any], privates: dict[str, dict[str, Any]]) -> dict[str, str]:
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    for agent_id in task["priority"]:
        private = privates[agent_id]
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


def solve(task: dict[str, Any], variant: str) -> dict[str, str]:
    return solve_from_privates(
        task,
        {"agent_a": agent_private(task, "agent_a", variant), "agent_b": agent_private(task, "agent_b", variant)},
    )


def oracle_plan(task: dict[str, Any], variant: str) -> dict[str, Any]:
    a = agent_private(task, "agent_a", variant)
    b = agent_private(task, "agent_b", variant)
    return {
        "plan_version": "plan-001",
        "initial_conflict": preferred_conflict_from(a["preferred"], b["preferred"]),
        "assignments": solve(task, variant),
        "rule": task["rule"],
        "resource_id": task["resource_id"],
    }
