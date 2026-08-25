"""L1 medium tasks. Two coupled rules, one registered revision. No L2 names."""

from __future__ import annotations

from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parent / "oracle"

_COMMON = (
    "必须在模块顶层写 SPEC_VERSION 和下面点名的常量。"
    "函数签名必须与任务一致，不要改参数名。"
    "不要输出 Markdown 围栏。不要只改版本号。"
)


def _aid(cap: int) -> str:
    return (
        "【工程师】王思远\n【职业】产品经理\n"
        "【任务】写 eligible(age, income)\n"
        f"【简报】年龄 >= 18 且收入 <= {cap} 才返回 True，否则 False。"
        f"常量 MIN_AGE = 18，INCOME_CAP = {cap}。"
        + _COMMON
    )


def _hours(limit: int) -> str:
    return (
        "【工程师】王思远\n【职业】产品经理\n"
        "【任务】写 can_work(certified, hours)\n"
        f"【简报】必须持证且本周工时 <= {limit} 才返回 True，否则 False。"
        f"常量 MAX_HOURS = {limit}。"
        + _COMMON
    )


def _route(threshold: int) -> str:
    return (
        "【工程师】王思远\n【职业】产品经理\n"
        "【任务】写 route(severity, center_closed)\n"
        "【简报】中心关闭时返回 None。"
        f"未关闭时，严重程度 >= {threshold} 返回 emergency，否则返回 standard。"
        f"常量 HIGH_PRIORITY_THRESHOLD = {threshold}。"
        + _COMMON
    )


TASKS = [
    {
        "id": "gm05b_aid_elig_001",
        "artifact": "aid_elig.py",
        "criterion_id": "income_cap",
        "symbol": "INCOME_CAP",
        "path": "income_cap",
        "parse": "int",
        "change_v1": {"income_cap": 50000},
        "change_v2": {"income_cap": 45000},
        "allow_names": {"SPEC_VERSION", "MIN_AGE", "INCOME_CAP"},
        "v1": {"brief": _aid(50000), "oracle": ORACLE_DIR / "test_aid_v1.py"},
        "v2": {"brief": _aid(45000), "oracle": ORACLE_DIR / "test_aid_v2.py"},
    },
    {
        "id": "gm05b_hours_cert_001",
        "artifact": "hours_cert.py",
        "criterion_id": "max_hours",
        "symbol": "MAX_HOURS",
        "path": "max_hours",
        "parse": "int",
        "change_v1": {"max_hours": 40},
        "change_v2": {"max_hours": 35},
        "allow_names": {"SPEC_VERSION", "MAX_HOURS"},
        "v1": {"brief": _hours(40), "oracle": ORACLE_DIR / "test_hours_v1.py"},
        "v2": {"brief": _hours(35), "oracle": ORACLE_DIR / "test_hours_v2.py"},
    },
    {
        "id": "gm05b_route_closed_001",
        "artifact": "route_closed.py",
        "criterion_id": "high_priority_threshold",
        "symbol": "HIGH_PRIORITY_THRESHOLD",
        "path": "high_priority_threshold",
        "parse": "int",
        "change_v1": {"high_priority_threshold": 7},
        "change_v2": {"high_priority_threshold": 6},
        "allow_names": {"SPEC_VERSION", "HIGH_PRIORITY_THRESHOLD"},
        "v1": {"brief": _route(7), "oracle": ORACLE_DIR / "test_route_v1.py"},
        "v2": {"brief": _route(6), "oracle": ORACLE_DIR / "test_route_v2.py"},
    },
]


def private_payload(task: dict, version: str) -> dict:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    return {
        "spec_version": version,
        "criterion_id": task["criterion_id"],
        "required_change": change,
        "instruction": (
            "根据草稿判断是否满足 required_change。"
            "满足则 decision=approve 且 required_change 为空；"
            "否则 decision=revise 并给出 required_change。不要改文件。"
        ),
    }
