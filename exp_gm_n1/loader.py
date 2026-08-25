from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("n1_bridge_status_001", "n1_ferry_status_001", "n1_warehouse_gate_001")
TRACKS = ("direct", "full", "drop")
VARIANTS = ("control", "intervention")


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["oracle"] = ROOT / "oracle" / f"{task_id}.json"
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def leak_tokens_for(task: dict[str, Any], variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return list(task.get("leak_tokens") or [])


def source_private(task: dict[str, Any], variant: str) -> dict[str, Any]:
    intervention = variant == "intervention"
    return {
        "source_id": task["source_id"],
        "reported_state": task["intervention_state"] if intervention else task["control_state"],
        "state_version": "v2" if intervention else "v1",
        "evidence_id": task["evidence_v2"] if intervention else task["evidence_v1"],
    }
