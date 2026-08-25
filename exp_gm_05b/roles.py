"""required_change prompts. No typed-patch. Hidden tests never enter prompts."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_04c.roles import parse_review_json
from exp_gm_05b.artifacts import render_source
from exp_gm_05b.inspect import registered_value, spec_version, values_match
from exp_gm_05b.tasks import private_payload


def rule_reviewer(draft: str, task: dict, private: dict[str, Any]) -> dict[str, Any]:
    required = dict(private.get("required_change") or {})
    required_version = str(private.get("spec_version") or "v1")
    got = registered_value(draft, task)
    version = spec_version(draft) or "v1"
    matches = version == required_version and values_match(got, required.get(task["path"]))
    if matches:
        return {
            "decision": "approve",
            "reviewed_spec_version": version,
            "required_spec_version": required_version,
            "criterion_id": task["criterion_id"],
            "evidence": "draft matches required_change",
            "required_change": {},
        }
    return {
        "decision": "revise",
        "reviewed_spec_version": version,
        "required_spec_version": required_version,
        "criterion_id": task["criterion_id"],
        "evidence": f"observed={got} required={required}",
        "required_change": required,
    }


def rule_executor(task: dict, *, review: dict[str, Any] | None, current: str) -> str:
    if review and review.get("decision") == "revise" and review.get("required_change"):
        return render_source(task, str(review.get("required_spec_version") or "v2"))
    return current


def reviewer_prompt(draft: str, private: dict[str, Any]) -> str:
    return (
        "你是代码审核员。只能根据登记标准和草稿做决定。不要改文件，不要编造隐藏测试。"
        "只输出 JSON：decision, reviewed_spec_version, required_spec_version, criterion_id, evidence, required_change。\n"
        f"【审查标准】{json.dumps(private, ensure_ascii=False)}\n【草稿】\n{draft[:4000]}\n"
    )


def self_check_prompt(draft: str, private: dict[str, Any]) -> str:
    return (
        "你正在自检一份固定初稿。不要编造隐藏测试。这一步不要改文件。"
        "只输出 JSON：decision, reviewed_spec_version, required_spec_version, criterion_id, evidence, required_change。\n"
        f"【当前验收要求】{json.dumps(private, ensure_ascii=False)}\n【草稿】\n{draft[:4000]}\n"
    )


def executor_prompt(brief: str, source: str, review: dict[str, Any] | None) -> str:
    extra = "\n【当前草稿】从这份草稿修改或确认。环境不会替你改文件。\n" + source[:4000]
    if review:
        extra += (
            "\n【审核意见】按 required_change 修改真实常量并更新 SPEC_VERSION。"
            "不要只改版本号，不要只写 APPLIED_PATCH_IDS。\n"
            + json.dumps(review, ensure_ascii=False)
        )
    return brief + extra + "\n只输出完整 Python 源码。\n"


def parse_review(text: str) -> dict[str, Any]:
    return parse_review_json(text)
