from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("cal_service_capacity_001", "cal_response_deadline_001", "cal_eligibility_age_001")
VARIANTS = ("control", "intervention")


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["oracle"] = ROOT / "oracle" / f"{task_id}.json"
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def required_value(task: dict[str, Any], variant: str) -> int:
    return int(task["control_required"] if variant == "control" else task["intervention_required"])
