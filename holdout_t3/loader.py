"""Load T3-03 tasks. Do not import T3-01/T3-02 development items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("t3_ho_queue_max_001", "t3_ho_battery_pct_001", "t3_ho_noise_db_001")
ORACLE = {
    "t3_ho_queue_max_001": ("test_t3ho_queue_v1.py", "test_t3ho_queue_v2.py"),
    "t3_ho_battery_pct_001": ("test_t3ho_batt_v1.py", "test_t3ho_batt_v2.py"),
    "t3_ho_noise_db_001": ("test_t3ho_noise_v1.py", "test_t3ho_noise_v2.py"),
}
TRACKS = ("single", "multi", "drop")
VARIANTS = ("control", "intervention")
DIRECT_TRACK = "direct"


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    v1_name, v2_name = ORACLE[task_id]
    payload["v1"] = {"oracle": ROOT / "oracle" / v1_name}
    payload["v2"] = {"oracle": ROOT / "oracle" / v2_name}
    payload["brief"] = _brief(payload, payload["change_v1"][payload["target"]])
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def _brief(task: dict[str, Any], value: int) -> str:
    return (
        "【工程师】陈可\n【职业】后台开发\n"
        f"【任务】写 {task['function']}\n"
        f"【简报】{task['brief_rule'].strip()} 常量 {task['symbol']} = {value}。SPEC_VERSION = \"v1\"。\n"
    )


def leak_tokens_for(task: dict[str, Any], variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return list(task.get("leak_tokens") or [])


def public_required(task: dict[str, Any]) -> Any:
    return task["change_v1"][task["target"]]
