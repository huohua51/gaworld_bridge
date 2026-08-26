"""Load and validate T4-01 registered tasks."""

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
    for task in tasks:
        route = list(task.get("path") or [])
        bridge = list(task.get("bridge") or [])
        if len(route) < 3 or len(bridge) != 2:
            raise ValueError(f"invalid topology for {task.get('id')}")
        pairs = [route[index : index + 2] for index in range(len(route) - 1)]
        if bridge not in pairs:
            raise ValueError(f"bridge is not on registered path for {task.get('id')}")
        if task.get("source") != route[0] or task.get("target") != route[-1]:
            raise ValueError(f"source/target mismatch for {task.get('id')}")
    return tasks


def payload_for(task: dict[str, Any], variant: str) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    return dict(task[f"{variant}_payload"])
