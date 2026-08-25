from __future__ import annotations

import json
import re
from typing import Any

from cal_gm_apply_01.inspect import parse_source
from cal_gm_apply_01.loader import review_payload


def rule_review(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return review_payload(task, variant)


def rule_executor(task: dict[str, Any], variant: str, source: str) -> str:
    text = source
    for change in review_payload(task, variant)["required_changes"]:
        pattern = rf"^{re.escape(change['path'])}\s*=\s*{re.escape(str(change['old_value']))}\s*$"
        text, n = re.subn(pattern, f"{change['path']} = {change['new_value']}", text, count=1, flags=re.M)
        if n != 1:
            raise AssertionError(f"rule executor missed {change['path']}")
    return text if text.endswith("\n") else text + "\n"


def executor_prompt(task: dict[str, Any], variant: str, source: str) -> str:
    review = rule_review(task, variant)
    return (
        "只输出完整 Python 源码。不要输出解释、Markdown 或其它文字。\n"
        "你是执行者。必须从【当前草稿】修改，不要从零编造无关文件。\n"
        "按 required_changes 把对应常量从 old_value 改成 new_value。\n"
        "不要改未出现在 required_changes 中的登记字段。环境不会替你改文件。\n"
        f"【修改要求】{json.dumps(review, ensure_ascii=False)}\n"
        "【当前草稿】\n"
        f"{source}"
    )


def strip_source(text: str) -> str:
    return parse_source(text)
