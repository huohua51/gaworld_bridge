"""Load the C1-06 fresh implementation-regression surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = (
    "c1_06_floodgate_inspection_001",
    "c1_06_vaccine_coldroom_001",
    "c1_06_theater_rehearsal_001",
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
