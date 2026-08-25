"""GM-05 development tasks. No 04e/04d ids or held-out field names."""

from __future__ import annotations

from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parent / "oracle"

_COMMON = (
    "必须在模块顶层写 SPEC_VERSION。"
    "门槛必须是模块常量，不要把隐藏测试写进代码。"
    "不要输出 Markdown 围栏。文件须可独立运行。"
    "不要只改版本号，也不要只写 APPLIED_PATCH_IDS。"
)


def _aid_brief(version: str, cap: int) -> str:
    return (
        "【工程师】王思远\n【职业】产品经理\n"
        "【任务】写应急援助分配模块：eligible(applicant) 与 allocate(applicants)\n"
        f"【简报】申请人须年满 18 岁、收入不超过 {cap}、并提供证明材料才合格。"
        "优先级 critical > high > standard。总预算 10000，按优先级顺序发放，预算不足则后面的人少给或不给。"
        f"模块常量 INCOME_CAP = {cap}。"
        + _COMMON
    )


def _roster_brief(version: str, night: int) -> str:
    return (
        "【工程师】王思远\n【职业】产品经理\n"
        "【任务】写排班模块：valid_roster(assignments, workers, shifts) 与 assign(workers, shifts)\n"
        "【简报】每个时段必须有人；medic 岗位必须持证；每人最长 12 小时；同一人不得占用相同 slot。"
        f"夜班 kind=night 的最低人数是 {night}。"
        f"模块常量 NIGHT_SHIFT_MINIMUM = {night}。"
        + _COMMON
    )


def _routing_brief(version: str, threshold: int) -> str:
    return (
        "【工程师】王思远\n【职业】产品经理\n"
        "【任务】写事件路由模块：is_high_priority(incident) 与 route(incident, centers)\n"
        f"【简报】严重程度 >= {threshold} 为高优先级，截止时间 2 小时，否则 8 小时。"
        "跳过关闭中心、容量已满的中心，以及地区不覆盖的中心。"
        f"模块常量 HIGH_PRIORITY_THRESHOLD = {threshold}。"
        + _COMMON
    )


TASKS = [
    {
        "id": "gm05_aid_allocation_001",
        "artifact": "aid_policy.py",
        "criterion_id": "income_cap",
        "symbol": "INCOME_CAP",
        "path": "income_cap",
        "parse": "int",
        "change_v1": {"income_cap": 50000},
        "change_v2": {"income_cap": 45000},
        "leak_tokens": ["INCOME_CAP = 45000", "收入不超过 45000"],
        "allow_names": {
            "SPEC_VERSION", "INCOME_CAP", "MIN_AGE", "TOTAL_BUDGET", "PROOF_REQUIRED", "_PRIORITY",
        },
        "v1": {"brief": _aid_brief("v1", 50000), "oracle": ORACLE_DIR / "test_aid_v1.py"},
        "v2": {"brief": _aid_brief("v2", 45000), "oracle": ORACLE_DIR / "test_aid_v2.py"},
    },
    {
        "id": "gm05_shift_roster_001",
        "artifact": "roster.py",
        "criterion_id": "night_shift_minimum",
        "symbol": "NIGHT_SHIFT_MINIMUM",
        "path": "night_shift_minimum",
        "parse": "int",
        "change_v1": {"night_shift_minimum": 1},
        "change_v2": {"night_shift_minimum": 2},
        "leak_tokens": ["NIGHT_SHIFT_MINIMUM = 2", "最低人数是 2"],
        "allow_names": {
            "SPEC_VERSION", "NIGHT_SHIFT_MINIMUM", "MAX_HOURS", "CERTIFIED_ROLES",
        },
        "v1": {"brief": _roster_brief("v1", 1), "oracle": ORACLE_DIR / "test_roster_v1.py"},
        "v2": {"brief": _roster_brief("v2", 2), "oracle": ORACLE_DIR / "test_roster_v2.py"},
    },
    {
        "id": "gm05_incident_routing_001",
        "artifact": "routing.py",
        "criterion_id": "high_priority_threshold",
        "symbol": "HIGH_PRIORITY_THRESHOLD",
        "path": "high_priority_threshold",
        "parse": "int",
        "change_v1": {"high_priority_threshold": 7},
        "change_v2": {"high_priority_threshold": 6},
        "leak_tokens": ["HIGH_PRIORITY_THRESHOLD = 6", "严重程度 >= 6"],
        "allow_names": {
            "SPEC_VERSION", "HIGH_PRIORITY_THRESHOLD", "DEADLINE_HOURS", "STANDARD_HOURS",
        },
        "v1": {"brief": _routing_brief("v1", 7), "oracle": ORACLE_DIR / "test_routing_v1.py"},
        "v2": {"brief": _routing_brief("v2", 6), "oracle": ORACLE_DIR / "test_routing_v2.py"},
    },
]


def private_payload(task: dict, version: str) -> dict:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return {
        "spec_version": version,
        "criterion_id": task["criterion_id"],
        "required_change": change,
        "instruction": (
            "根据草稿源码判断它是否满足 required_change。"
            "满足则 decision=approve 且 required_change 为空；"
            "否则 decision=revise 并给出 required_change。"
            "不要改文件，只输出一个 JSON 对象。"
        ),
    }


def leak_tokens_for(task: dict, variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return list(task.get("leak_tokens") or [])
