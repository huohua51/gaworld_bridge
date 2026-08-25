from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = (
    "cal_apply_limit_fallback_001",
    "cal_apply_weekday_weekend_001",
    "cal_apply_normal_emergency_001",
)
VARIANTS = ("control", "intervention")


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["draft"] = str(payload["draft"]).replace("\r\n", "\n")
    if not payload["draft"].endswith("\n"):
        payload["draft"] += "\n"
    payload["oracle_control"] = ROOT / "oracle" / f"test_{task_id}_control.py"
    payload["oracle_intervention"] = ROOT / "oracle" / f"test_{task_id}_intervention.py"
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def required_changes(task: dict[str, Any], variant: str) -> list[dict[str, Any]]:
    current = int(task["current"])
    want = int(task["required"])
    changes = [{"path": task["primary"], "old_value": current, "new_value": want}]
    if variant == "intervention":
        changes.append({"path": task["secondary"], "old_value": current, "new_value": want})
    return changes


def review_payload(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return {"decision": "update", "required_changes": required_changes(task, variant)}


def fact_specs(task: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"symbol": task["primary"], "criterion_path": task["primary"], "parse": "int"},
        {"symbol": task["secondary"], "criterion_path": task["secondary"], "parse": "int"},
    ]
