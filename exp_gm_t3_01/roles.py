"""Prompts and Rule agents. Hidden tests never enter prompts."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_t3_01.artifacts import render_source
from exp_gm_t3_01.contracts.review_action import APPROVE, REVISE
from exp_gm_t3_01.inspect import registered_value, spec_version, values_match
from exp_gm_t3_01.loader import private_payload


def rule_builder_draft(task: dict) -> str:
    return render_source(task, "v1")


def rule_builder_revise(task: dict, *, review: dict[str, Any] | None, current: str) -> str:
    if not review or review.get("action") != REVISE:
        return current
    if values_match(review.get("required_value"), task["change_v2"][task["target"]]) and review.get("target") == task["target"]:
        return render_source(task, "v2")
    return current


def rule_reviewer(draft: str, task: dict, private: dict[str, Any]) -> dict[str, Any]:
    got = registered_value(draft, task)
    want = private.get("required_value")
    evidence = str(private.get("evidence_id") or "")
    version = spec_version(draft) or "v1"
    if version == str(private.get("spec_version") or "v1") and values_match(got, want):
        return {"action": APPROVE, "evidence_id": evidence}
    return {
        "action": REVISE,
        "target": private.get("target") or task["target"],
        "required_value": want,
        "evidence_id": evidence,
    }


def builder_draft_prompt(brief: str) -> str:
    return brief + "只输出完整 Python 源码。\n"


def builder_revise_prompt(brief: str, source: str, review: dict[str, Any] | None) -> str:
    extra = "\n【当前草稿】从这份草稿修改或确认。环境不会替你改文件。\n" + source[:4000]
    if review:
        extra += (
            "\n【审核意见】若 action=request_revision，把登记常量改成 required_value，并更新 SPEC_VERSION。"
            "不要只改版本号，不要只写 APPLIED_PATCH_IDS。approve_draft 时保持原文件。\n"
            + json.dumps(review, ensure_ascii=False)
        )
    return brief + extra + "\n只输出完整 Python 源码。\n"


def review_schema_block() -> str:
    return (
        "只输出一个 JSON 对象。不要输出解释、Markdown、代码或其它文字。\n"
        "对象只能包含已登记字段，不能多键。\n"
        f'批准只能是：{{"action": "{APPROVE}", "evidence_id": "<登记 evidence_id>"}}\n'
        "批准时禁止出现 target 和 required_value。\n"
        f'要求修改只能是：{{"action": "{REVISE}", "target": "<登记 target>", '
        '"required_value": <数字>, "evidence_id": "<登记 evidence_id>"}}\n'
        "禁止输出 decision、mismatches、required_change、NONE，以及任何未登记键。\n"
    )


def self_check_prompt(draft: str, private: dict[str, Any]) -> str:
    return (
        review_schema_block()
        + "你正在自检刚才写的代码。只能根据当前验收要求和草稿做决定。"
        "不要编造隐藏测试，这一步不要改文件。\n"
        f"【当前验收要求】{json.dumps(private, ensure_ascii=False)}\n【草稿】\n{draft[:4000]}\n"
    )


def reviewer_prompt(draft: str, private: dict[str, Any]) -> str:
    return (
        review_schema_block()
        + "你是代码审核员。只能根据登记标准和草稿做决定。不要改文件，不要编造隐藏测试。\n"
        f"【审查标准】{json.dumps(private, ensure_ascii=False)}\n【草稿】\n{draft[:4000]}\n"
    )


def current_private(task: dict, variant: str) -> dict[str, Any]:
    return private_payload(task, variant)
