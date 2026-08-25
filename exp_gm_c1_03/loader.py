"""C1-03 tasks. Not C1-01 / COMP / REPAIR / C1-02 / PRIORITY items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("c1_03_electrophoresis_001", "c1_03_cryostat_001", "c1_03_incubator_shelf_001")
TRACKS = ("multi", "drop_protection", "drop_coordinator")
VARIANTS = ("control", "intervention")
RULE_TEXT = (
    "先给高优先级 Agent 分配其 preferred（须在其可行集内且空闲）；"
    "再给低优先级 Agent 按其可行集列表顺序选择第一个空闲时段。"
    "禁止把未出现在该 Agent 可行集中的时段分配给该 Agent。"
    "登记保护修订后，被保护的高优先级原分配必须保留；只调整低优先级。"
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
    "c1_02_optics_table_001",
    "c1_02_greenhouse_001",
    "c1_02_cold_store_001",
    "c1_02_uav_pad_001",
    "c1prio_mass_spec_001",
    "c1prio2_hplc_001",
    "c1prio2_gown_001",
    "c1prio2_vivarium_001",
    "charger_A",
    "mill_01",
    "dock_1",
    "locker_bay",
    "lab_bench",
    "van_bay",
    "pump_hose",
    "radio_desk",
    "ferry_berth",
    "optics_table",
    "h8",
    "k1",
    "w08",
    "ms41",
    "hc51",
    "ga61",
    "vb71",
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


def phase1_priority(task: dict[str, Any], variant: str) -> list[str]:
    return list(task["phase1"][variant]["priority"])


def protection_spec(task: dict[str, Any]) -> dict[str, Any]:
    return dict(task["protection"])


def _pack_private(task: dict[str, Any], agent_id: str, block: dict[str, Any], variant: str) -> dict[str, Any]:
    feasible = list(block["feasible"])
    high = phase1_priority(task, variant)[0]
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
        "window_token": str(block.get("window_token") or ("a_window_v1" if agent_id == "agent_a" else "b_window_v1")),
        "window_key": "+".join(feasible),
        "priority": "high" if agent_id == high else "low",
    }


def agent_private(task: dict[str, Any], agent_id: str, variant: str) -> dict[str, Any]:
    if agent_id == "agent_a":
        block = {
            "label": task["agent_a"].get("label"),
            "feasible": list(task["agent_a"]["feasible"]),
            "preferred": task["agent_a"][variant]["preferred"],
        }
        return _pack_private(task, agent_id, block, variant)
    return _pack_private(task, agent_id, dict(task["agent_b"][variant]), variant)


def public_spec(task: dict[str, Any], variant: str, *, after_protection: bool = False) -> dict[str, Any]:
    priority = ["agent_a", "agent_b"] if after_protection else phase1_priority(task, variant)
    return {
        "resource_id": task["resource_id"],
        "slots": list(task["slots"]),
        "priority": priority,
        "rule": task["rule"],
        "rule_text": RULE_TEXT,
    }


def _solve_with_priority(priority: list[str], privates: dict[str, dict[str, Any]]) -> dict[str, str]:
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    for agent_id in priority:
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


def privates_for(task: dict[str, Any], variant: str) -> dict[str, dict[str, Any]]:
    return {
        "agent_a": agent_private(task, "agent_a", variant),
        "agent_b": agent_private(task, "agent_b", variant),
    }


def solve_phase1(task: dict[str, Any], variant: str, privates: dict[str, dict[str, Any]] | None = None) -> dict[str, str]:
    body = privates or privates_for(task, variant)
    return _solve_with_priority(phase1_priority(task, variant), body)


def solve_final(task: dict[str, Any], variant: str, privates: dict[str, dict[str, Any]] | None = None) -> dict[str, str]:
    body = privates or privates_for(task, variant)
    protected = protection_spec(task)
    a_slot = str(protected["slot"])
    occupied = {a_slot}
    b_feasible = list(body["agent_b"]["feasible"])
    b_slot = next((item for item in b_feasible if item not in occupied), "")
    return {"agent_a": a_slot, "agent_b": b_slot}


def oracle_plan(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return {
        "plan_version": "plan-001",
        "nack_expected": bool(task["oracle"][variant]["nack_expected"]),
        "first": dict(task["oracle"][variant]["first"]),
        "assignments": dict(task["oracle"][variant]["assignments"]),
        "rule": task["rule"],
        "resource_id": task["resource_id"],
    }


def repair_slot_for(task: dict[str, Any], variant: str) -> str:
    return str(task["oracle"][variant]["assignments"]["agent_b"])
