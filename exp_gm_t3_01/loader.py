"""Load T3-01 tasks. New L1 items only; GM-05 tasks are not imported."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("t3_parking_threshold_001", "t3_deposit_ratio_001", "t3_queue_cap_001")
ORACLE = {
    "t3_parking_threshold_001": ("test_parking_v1.py", "test_parking_v2.py"),
    "t3_deposit_ratio_001": ("test_deposit_v1.py", "test_deposit_v2.py"),
    "t3_queue_cap_001": ("test_queue_v1.py", "test_queue_v2.py"),
}
TRACKS = ("single", "multi", "drop")
VARIANTS = ("control", "intervention")


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
        "【工程师】林晓\n【职业】后台开发\n"
        f"【任务】写 {task['function']}\n"
        f"【简报】{task['brief_rule'].strip()} 常量 {task['symbol']} = {value}。SPEC_VERSION = \"v1\"。\n"
    )


def leak_tokens_for(task: dict[str, Any], variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return list(task.get("leak_tokens") or [])


def private_payload(task: dict[str, Any], variant: str) -> dict[str, Any]:
    version = "v1" if variant == "control" else "v2"
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return {
        "spec_version": version,
        "criterion_id": task["criterion_id"],
        "target": task["target"],
        "required_value": change[task["target"]],
        "evidence_id": task["evidence_v1"] if version == "v1" else task["evidence_v2"],
        "instruction": (
            "草稿已满足 required_value 时输出 approve_draft；"
            "否则输出 request_revision。不要改文件，不要编造隐藏测试。"
        ),
    }
