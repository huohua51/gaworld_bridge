"""Fresh REL1-v2 sources, histories, and frozen expected transitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = (
    "rel1_02_flood_gate_001",
    "rel1_02_cold_chain_001",
    "rel1_02_ferry_service_001",
)
VARIANTS = ("control", "intervention")


def load_task(task_id: str) -> dict[str, Any]:
    task = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    task["oracle"] = json.loads((ROOT / "oracle" / f"{task_id}.json").read_text(encoding="utf-8"))
    return task


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def current_signals(task: dict[str, Any]) -> list[dict[str, str]]:
    return [dict(item) for item in task["current_signals"]]


def history_for(task: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    return [dict(item) for item in task["history"][variant]]


def latest_row(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return dict(task["latest_outcome"][variant])
