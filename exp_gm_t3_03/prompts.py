"""T3-02 CHANGE/APPLY prompts, split by whether the private spec is visible."""

from __future__ import annotations

import json
import re
from typing import Any

from cal_gm_apply_01.inspect import parse_source
from cal_gm_change_01.contract import KEEP, UPDATE
from exp_gm_t3_01.inspect import registered_value, values_match
from exp_gm_t3_01.roles import builder_draft_prompt
from exp_gm_t3_02.contract import canonicalize
from exp_gm_t3_03.artifacts import render_source
from exp_gm_t3_03.loader import public_required


def observed_value(task: dict[str, Any], source: str) -> Any:
    return registered_value(source, task)


def required_value(task: dict[str, Any], variant: str) -> Any:
    change = task["change_v1"] if variant == "control" else task["change_v2"]
    return change[task["target"]]


def visible_required(task: dict[str, Any], variant: str, *, private_visible: bool) -> Any:
    if private_visible:
        return required_value(task, variant)
    return public_required(task)


def rule_review(task: dict[str, Any], variant: str, draft: str, *, private_visible: bool) -> dict[str, Any]:
    observed = observed_value(task, draft)
    required = visible_required(task, variant, private_visible=private_visible)
    evidence = {"path": task["symbol"], "observed": observed, "required": required}
    if values_match(observed, required):
        return {"decision": KEEP, "evidence": evidence, "required_changes": []}
    return {
        "decision": UPDATE,
        "evidence": evidence,
        "required_changes": [
            {
                "change_id": "change-01",
                "path": task["symbol"],
                "old_value": observed,
                "new_value": required,
            }
        ],
    }


def rule_executor(task: dict[str, Any], source: str, review: dict[str, Any] | None) -> str:
    if not review:
        return source if source.endswith("\n") else source + "\n"
    text = source
    for change in review.get("required_changes") or []:
        pattern = rf"^{re.escape(str(change['path']))}\s*=\s*{re.escape(str(change['old_value']))}\s*$"
        text, n = re.subn(pattern, f"{change['path']} = {change['new_value']}", text, count=1, flags=re.M)
        if n != 1:
            continue
    return text if text.endswith("\n") else text + "\n"


def rule_builder_draft(task: dict[str, Any]) -> str:
    return render_source(task, "v1")


def reviewer_prompt(task: dict[str, Any], variant: str, draft: str, *, private_visible: bool, self_check: bool) -> str:
    observed = observed_value(task, draft)
    required = visible_required(task, variant, private_visible=private_visible)
    keep_ex = {
        "decision": KEEP,
        "evidence": {"path": task["symbol"], "observed": observed, "required": observed},
        "required_changes": [],
    }
    if self_check:
        role = "你正在自检刚才写的代码。只能根据当前可见验收要求和草稿做决定。这一步不要改文件。\n"
    elif private_visible:
        role = "你是代码审核员。你持有本轮私有核验标准。只能根据登记标准和草稿做决定。不要改文件。\n"
    else:
        role = "你是代码审核员。只能根据公开简报和草稿做决定。不要改文件。\n"
    if private_visible:
        standard = (
            f"【私有核验】{task['symbol']} = {required}\n"
            f"【当前值】{observed}\n"
            f"【本轮要求值】{required}\n"
            "当前值已经等于要求值时输出 keep；当前值与要求值冲突时输出 update。\n"
        )
    else:
        standard = (
            f"【当前值】{observed}\n"
            f"【公开简报要求】{required}\n"
            "只能根据公开简报和当前草稿。没有其它核验材料。不要编造未给出的新标准。\n"
            "当前值已经等于公开简报要求时输出 keep。\n"
        )
    return (
        "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
        "decision 只能是 keep 或 update。\n"
        "keep 时 required_changes 必须是 []，不能带修改字段。\n"
        "update 时 required_changes 必须包含 path、old_value、new_value。\n"
        "evidence 必须包含 path、observed、required。observed 必须等于当前值，required 必须等于你看到的要求值。\n"
        f"keep 示例：{json.dumps(keep_ex, ensure_ascii=False)}\n"
        'update 示例：{"decision": "update", "evidence": {"path": "<path>", "observed": <当前值>, '
        '"required": <要求值>}, "required_changes": [{"change_id": "change-01", "path": "<path>", '
        '"old_value": <当前值>, "new_value": <要求值>}]}\n'
        + role
        + f"【登记字段】{task['symbol']}\n"
        + standard
        + f"【草稿】\n{draft[:4000]}\n"
    )


def executor_prompt(source: str, review: dict[str, Any] | None) -> str:
    if review is None:
        return (
            "只输出完整 Python 源码。不要输出解释、Markdown 或其它文字。\n"
            "你是执行者。必须从【当前草稿】修改或确认，不要从零编造无关文件。\n"
            "没有收到修改要求。确认并提交当前草稿。环境不会替你改文件。\n"
            "【当前草稿】\n"
            f"{source}"
        )
    payload = canonicalize(review) if review.get("decision") else review
    return (
        "只输出完整 Python 源码。不要输出解释、Markdown 或其它文字。\n"
        "你是执行者。必须从【当前草稿】修改，不要从零编造无关文件。\n"
        "按 required_changes 把对应常量从 old_value 改成 new_value。\n"
        "不要改未出现在 required_changes 中的登记字段。环境不会替你改文件。\n"
        f"【修改要求】{json.dumps(payload, ensure_ascii=False)}\n"
        "【当前草稿】\n"
        f"{source}"
    )


def draft_prompt(task: dict[str, Any]) -> str:
    return builder_draft_prompt(task["brief"])


def strip_source(text: str) -> str:
    return parse_source(text)
