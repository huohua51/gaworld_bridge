"""Load the REL1-04 fresh implementation-regression surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = (
    "rel1_04_ferry_channel_001",
    "rel1_04_hospital_oxygen_001",
    "rel1_04_museum_humidity_001",
)
VARIANTS = ("control", "intervention")


def load_task(task_id: str) -> dict[str, Any]:
    task = yaml.safe_load(
        (ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8")
    )
    task["oracle"] = json.loads(
        (ROOT / "oracle" / f"{task_id}.json").read_text(encoding="utf-8")
    )
    return task


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]
