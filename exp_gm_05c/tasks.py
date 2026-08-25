"""Reuse frozen 05b L1 tasks. Do not edit exp_gm_05b task files."""

from __future__ import annotations

from exp_gm_05b.tasks import TASKS as L1_TASKS
from exp_gm_05b.tasks import private_payload

LEAK_TOKENS = {
    "gm05b_aid_elig_001": ["INCOME_CAP = 45000", "收入 <= 45000"],
    "gm05b_hours_cert_001": ["MAX_HOURS = 35", "工时 <= 35"],
    "gm05b_route_closed_001": ["HIGH_PRIORITY_THRESHOLD = 6", "严重程度 >= 6"],
}

TASKS = [{**dict(task), "leak_tokens": list(LEAK_TOKENS[task["id"]])} for task in L1_TASKS]


def leak_tokens_for(task: dict, variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return list(task.get("leak_tokens") or [])
