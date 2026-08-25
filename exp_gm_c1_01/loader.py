"""Load C1-01 tasks. Do not import T3 or N1 items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("c1_charge_slot_001", "c1_device_book_001", "c1_dock_window_001")
TRACKS = ("single", "multi", "drop")
VARIANTS = ("control", "intervention")
AGENTS = ("agent_a", "agent_b")
RULE_TEXT = "优先级高的 Agent 保留原时段（若可行且空闲）；优先级低的 Agent 使用最早可行空闲替代时段。"


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


def agent_private(task: dict[str, Any], agent_id: str, variant: str) -> dict[str, Any]:
    if agent_id == "agent_a":
        block = dict(task["agent_a"])
        feasible = list(block["feasible"])
        preferred = block["preferred"]
        token = "a_window_v1"
        window_key = "+".join(feasible)
    else:
        block = dict(task["agent_b"][variant])
        feasible = list(block["feasible"])
        preferred = block["preferred"]
        token = str(block.get("window_token") or "")
        window_key = "+".join(feasible)
    return {
        "agent_id": agent_id,
        "label": block.get("label") or agent_id,
        "resource_id": task["resource_id"],
        "feasible": feasible,
        "preferred": preferred,
        "window_token": token,
        "window_key": window_key,
        "priority": "high" if agent_id == "agent_a" else "low",
    }


def public_spec(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": task["resource_id"],
        "slots": list(task["slots"]),
        "priority": list(task["priority"]),
        "rule": task["rule"],
        "rule_text": RULE_TEXT,
    }


def preferred_conflict(task: dict[str, Any], variant: str) -> bool:
    a = agent_private(task, "agent_a", variant)
    b = agent_private(task, "agent_b", variant)
    return a["preferred"] == b["preferred"]


def solve(task: dict[str, Any], variant: str) -> dict[str, str]:
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    for agent_id in task["priority"]:
        private = agent_private(task, agent_id, variant)
        preferred = private["preferred"]
        if preferred in private["feasible"] and preferred not in occupied:
            slot = preferred
        else:
            slot = next((item for item in private["feasible"] if item not in occupied), "")
        assignments[agent_id] = slot
        if slot:
            occupied.add(slot)
    return assignments


def oracle_plan(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return {
        "plan_version": "plan-001",
        "conflict": preferred_conflict(task, variant),
        "assignments": solve(task, variant),
        "rule": task["rule"],
        "resource_id": task["resource_id"],
    }
