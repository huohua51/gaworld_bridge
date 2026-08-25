from __future__ import annotations

import json
from typing import Any

from cal_gm_change_01.contract import KEEP, UPDATE
from cal_gm_change_01.loader import required_value


def rule_agent(task: dict[str, Any], variant: str) -> dict[str, Any]:
    observed = int(task["current"])
    required = required_value(task, variant)
    evidence = {"path": task["path"], "observed": observed, "required": required}
    if observed == required:
        return {"decision": KEEP, "evidence": evidence, "required_change": None}
    return {
        "decision": UPDATE,
        "evidence": evidence,
        "required_change": {"path": task["path"], "old_value": observed, "new_value": required},
    }


def agent_prompt(task: dict[str, Any], variant: str) -> str:
    observed = int(task["current"])
    required = required_value(task, variant)
    keep_ex = {"decision": KEEP, "evidence": {"path": task["path"], "observed": observed, "required": observed}, "required_change": None}
    return (
        "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
        "decision 只能是 keep 或 update。\n"
        "keep 时 required_change 必须是 null，不能带修改字段。\n"
        "update 时 required_change 必须包含 path、old_value、new_value。\n"
        "evidence 必须包含 path、observed、required。observed 必须等于当前值，required 必须等于本轮要求值。\n"
        f"keep 示例：{json.dumps(keep_ex, ensure_ascii=False)}\n"
        'update 示例：{"decision": "update", "evidence": {"path": "<path>", "observed": <当前值>, '
        '"required": <要求值>}, "required_change": {"path": "<path>", "old_value": <当前值>, "new_value": <要求值>}}\n'
        f"【登记字段】{task['path']}\n"
        f"【当前值】{observed}\n"
        f"【本轮要求值】{required}\n"
        "当前值已经等于要求值时输出 keep；当前值与要求值冲突时输出 update。\n"
    )
