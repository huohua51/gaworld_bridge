"""TASK-W1-revision briefs. Thresholds are baked into the function, not passed as args."""

from __future__ import annotations

from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parent / "oracle"

_COMMON = (
    "必须在模块顶层写 SPEC_VERSION = \"{version}\"。"
    "门槛写死为代码常量，函数只接收下面写明的那一个参数。"
    "不要再接收门槛本身作为参数。不要输出 Markdown 围栏。文件须可独立运行。"
)


def _wage(version: str, threshold: int) -> str:
    return (
        f"【工程师】王思远\n【职业】产品经理\n"
        f"【任务】写 decide(take_home)，比较到手月薪与保留工资 {threshold}\n"
        f"【简报】到手 >= {threshold} 返回 accept，否则 reject。"
        + _COMMON.format(version=version)
    )


def _ret(version: str, rate: float) -> str:
    return (
        f"【工程师】王思远\n【职业】产品经理\n"
        f"【任务】写 min_return(principal)，最低返还率 {rate}\n"
        f"【简报】返回 int(principal * {rate})，向下取整。rate 不要当参数。"
        + _COMMON.format(version=version)
    )


def _budget(version: str, budget: int) -> str:
    return (
        f"【工程师】王思远\n【职业】产品经理\n"
        f"【任务】写 remaining(spent)，总预算 {budget}\n"
        f"【简报】返回 max(0, {budget} - spent)。预算不要当参数。"
        + _COMMON.format(version=version)
    )


TASKS = [
    {
        "id": "w1_wage_gate",
        "v1": {"brief": _wage("v1", 60000), "oracle": ORACLE_DIR / "test_wage_v1.py", "threshold": 60000},
        "v2": {"brief": _wage("v2", 70000), "oracle": ORACLE_DIR / "test_wage_v2.py", "threshold": 70000},
        "n_tests": 3,
    },
    {
        "id": "w1_return_floor",
        "v1": {"brief": _ret("v1", 0.3), "oracle": ORACLE_DIR / "test_return_v1.py", "threshold": 0.3},
        "v2": {"brief": _ret("v2", 0.5), "oracle": ORACLE_DIR / "test_return_v2.py", "threshold": 0.5},
        "n_tests": 3,
    },
    {
        "id": "w1_budget_remaining",
        "v1": {"brief": _budget("v1", 100), "oracle": ORACLE_DIR / "test_budget_v1.py", "threshold": 100},
        "v2": {"brief": _budget("v2", 80), "oracle": ORACLE_DIR / "test_budget_v2.py", "threshold": 80},
        "n_tests": 3,
    },
]
