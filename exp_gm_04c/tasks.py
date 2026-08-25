"""04c reuses 04b oracles. Reviewer only sees registered criteria, not pytest."""

from __future__ import annotations

from exp_gm_04b.tasks import TASKS as _BASE

CRITERIA = {
    "w1_wage_gate": {
        "criterion_id": "reservation_wage_threshold",
        "change_v1": {"reservation_wage": 60000},
        "change_v2": {"reservation_wage": 70000},
        "leak_tokens": ["70000"],
    },
    "w1_return_floor": {
        "criterion_id": "min_return_rate",
        "change_v1": {"min_return_rate": 0.3},
        "change_v2": {"min_return_rate": 0.5},
        "leak_tokens": ["0.5"],
    },
    "w1_budget_remaining": {
        "criterion_id": "total_budget",
        "change_v1": {"total_budget": 100},
        "change_v2": {"total_budget": 80},
        "leak_tokens": ["总预算 80", "THRESHOLD = 80", "BUDGET = 80"],
    },
}

TASKS = []
for item in _BASE:
    meta = CRITERIA[item["id"]]
    TASKS.append({**item, **meta})


def private_payload(task: dict, version: str) -> dict:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return {
        "spec_version": version,
        "criterion_id": task["criterion_id"],
        "required_change": change,
        "instruction": (
            "根据草稿源码判断它是否满足 required_change。"
            "满足则 decision=approve，否则 decision=revise 并给出 required_change。"
            "不要改文件，只输出一个 JSON 对象。"
        ),
    }


def leak_tokens_for(task: dict, variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return list(task.get("leak_tokens") or [])
