"""TASK-W1-lite briefs. Hidden tests live in oracle/ and are not in these strings."""

from __future__ import annotations

from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parent / "oracle"

TASKS = [
    {
        "id": "w1_wage_gate",
        "title": "写一个保留工资决策脚本",
        "brief": (
            "【工程师】王思远\n"
            "【职业】产品经理\n"
            "【任务】写一个独立 Python 脚本，实现函数 decide(reservation_wage, take_home)\n"
            "【简报】规则：到手月薪不低于保留工资时返回字符串 accept，否则返回 reject。"
            "文件须可独立运行。不要输出 Markdown 围栏。"
        ),
        "oracle": ORACLE_DIR / "test_w1_wage_gate.py",
        "n_tests": 4,
    },
    {
        "id": "w1_return_floor",
        "title": "写一个最低返还额脚本",
        "brief": (
            "【工程师】王思远\n"
            "【职业】产品经理\n"
            "【任务】写一个独立 Python 脚本，实现函数 min_return(principal, min_rate)\n"
            "【简报】返回整数最低返还额：principal * min_rate，向下取整。"
            "min_rate=0 时返回 0。文件须可独立运行。"
        ),
        "oracle": ORACLE_DIR / "test_w1_return_floor.py",
        "n_tests": 4,
    },
    {
        "id": "w1_budget_remaining",
        "title": "写一个预算余额脚本",
        "brief": (
            "【工程师】王思远\n"
            "【职业】产品经理\n"
            "【任务】写一个独立 Python 脚本，实现函数 remaining(budget, spent)\n"
            "【简报】返回尚未花掉的预算。若 spent 超过 budget，返回 0，不得出现负数。"
            "文件须可独立运行。"
        ),
        "oracle": ORACLE_DIR / "test_w1_budget_remaining.py",
        "n_tests": 4,
    },
]
