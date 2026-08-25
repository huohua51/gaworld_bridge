"""04d development vs held-out tasks. Protocol templates must not name Oracle fields."""

from __future__ import annotations

from pathlib import Path

from exp_gm_04c.tasks import TASKS as _DEV, leak_tokens_for, private_payload

ORACLE_DIR = Path(__file__).resolve().parent / "oracle"

DEV_TASKS = [{**item, "split": "development"} for item in _DEV]

_HELD_COMMON = (
    "必须在模块顶层写 SPEC_VERSION = \"{version}\"。"
    "门槛写死为代码常量，函数只接收下面写明的那一个参数。"
    "不要再接收门槛本身作为参数。不要输出 Markdown 围栏。文件须可独立运行。"
)


def _ship(version: str, threshold: int) -> str:
    return (
        f"【工程师】王思远\n【职业】产品经理\n"
        f"【任务】写 can_ship(weight)，重量不超过 {threshold} 才能发货\n"
        f"【简报】weight <= {threshold} 返回 ship，否则 hold。"
        + _HELD_COMMON.format(version=version)
    )


def _age(version: str, age: int) -> str:
    return (
        f"【工程师】王思远\n【职业】产品经理\n"
        f"【任务】写 eligible(age)，年龄达到 {age} 才合格\n"
        f"【简报】age >= {age} 返回 yes，否则 no。"
        + _HELD_COMMON.format(version=version)
    )


def _stock(version: str, point: int) -> str:
    return (
        f"【工程师】王思远\n【职业】产品经理\n"
        f"【任务】写 reorder(stock)，库存降到 {point} 及以下要补货\n"
        f"【简报】stock <= {point} 返回 buy，否则 wait。"
        + _HELD_COMMON.format(version=version)
    )


HELD_OUT_TASKS = [
    {
        "id": "shipping_threshold",
        "split": "held_out",
        "criterion_id": "shipping_threshold",
        "const": "THRESHOLD",
        "path": "shipping_threshold",
        "parse": "int",
        "fn": "can_ship",
        "change_v1": {"shipping_threshold": 99},
        "change_v2": {"shipping_threshold": 129},
        "leak_tokens": ["129"],
        "v1": {"brief": _ship("v1", 99), "oracle": ORACLE_DIR / "test_ship_v1.py", "threshold": 99},
        "v2": {"brief": _ship("v2", 129), "oracle": ORACLE_DIR / "test_ship_v2.py", "threshold": 129},
        "n_tests": 3,
        "template": (
            'SPEC_VERSION = "{version}"\nTHRESHOLD = {value}\n\n'
            "def can_ship(weight):\n"
            '    return "ship" if weight <= THRESHOLD else "hold"\n'
        ),
    },
    {
        "id": "eligibility_age",
        "split": "held_out",
        "criterion_id": "eligibility_age",
        "const": "AGE",
        "path": "eligibility_age",
        "parse": "int",
        "fn": "eligible",
        "change_v1": {"eligibility_age": 18},
        "change_v2": {"eligibility_age": 21},
        "leak_tokens": ["21"],
        "v1": {"brief": _age("v1", 18), "oracle": ORACLE_DIR / "test_age_v1.py", "threshold": 18},
        "v2": {"brief": _age("v2", 21), "oracle": ORACLE_DIR / "test_age_v2.py", "threshold": 21},
        "n_tests": 3,
        "template": (
            'SPEC_VERSION = "{version}"\nAGE = {value}\n\n'
            "def eligible(age):\n"
            '    return "yes" if age >= AGE else "no"\n'
        ),
    },
    {
        "id": "inventory_reorder_point",
        "split": "held_out",
        "criterion_id": "inventory_reorder_point",
        "const": "POINT",
        "path": "inventory_reorder_point",
        "parse": "int",
        "fn": "reorder",
        "change_v1": {"inventory_reorder_point": 10},
        "change_v2": {"inventory_reorder_point": 15},
        "leak_tokens": ["15"],
        "v1": {"brief": _stock("v1", 10), "oracle": ORACLE_DIR / "test_stock_v1.py", "threshold": 10},
        "v2": {"brief": _stock("v2", 15), "oracle": ORACLE_DIR / "test_stock_v2.py", "threshold": 15},
        "n_tests": 3,
        "template": (
            'SPEC_VERSION = "{version}"\nPOINT = {value}\n\n'
            "def reorder(stock):\n"
            '    return "buy" if stock <= POINT else "wait"\n'
        ),
    },
]

ALL_TASKS = DEV_TASKS + HELD_OUT_TASKS


__all__ = [
    "ALL_TASKS",
    "DEV_TASKS",
    "HELD_OUT_TASKS",
    "leak_tokens_for",
    "private_payload",
]
