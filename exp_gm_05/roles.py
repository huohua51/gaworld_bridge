"""required_change prompts. Do not use typed-patch. Hidden tests never enter prompts."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_04c.roles import parse_review_json
from exp_gm_05.artifacts import render_source
from exp_gm_05.inspect import registered_value, spec_version, values_match
from exp_gm_05.tasks import private_payload


def rule_reviewer(draft_source: str, task: dict, private: dict[str, Any]) -> dict[str, Any]:
    required = dict(private.get("required_change") or {})
    required_version = str(private.get("spec_version") or "v1")
    got = {task["path"]: registered_value(draft_source, task)}
    version = spec_version(draft_source) or "v1"
    matches = version == required_version and values_match(got.get(task["path"]), required.get(task["path"]))
    if matches:
        return {
            "decision": "approve",
            "reviewed_spec_version": version,
            "required_spec_version": required_version,
            "criterion_id": private.get("criterion_id") or task["criterion_id"],
            "evidence": "draft matches required_change",
            "required_change": {},
        }
    return {
        "decision": "revise",
        "reviewed_spec_version": version,
        "required_spec_version": required_version,
        "criterion_id": private.get("criterion_id") or task["criterion_id"],
        "evidence": f"observed={got} required={required}",
        "required_change": required,
    }


def rule_executor(task: dict, *, version: str, review: dict[str, Any] | None = None, current: str | None = None) -> str:
    if review and review.get("decision") == "revise" and review.get("required_change"):
        return render_source(task, str(review.get("required_spec_version") or "v2"))
    if current:
        return current
    return render_source(task, version)


def executor_prompt(brief_text: str, source: str | None = None, review: dict[str, Any] | None = None) -> str:
    extra = ""
    if source:
        extra += "\n【当前草稿】从这份草稿修改或确认。环境不会替你改文件。\n" + source[:6000]
    if review:
        extra += (
            "\n【审核意见】必须采用下面已送达的审核。按 required_change 修改真实常量，并更新 SPEC_VERSION。"
            "不要只改版本号，不要只写 APPLIED_PATCH_IDS。\n"
            + json.dumps(review, ensure_ascii=False)
        )
    return brief_text + extra + "\n只输出完整 Python 源码。\n"


def reviewer_prompt(draft_source: str, private: dict[str, Any]) -> str:
    return (
        "你是代码审核员。只能根据登记的审查标准和草稿源码做决定。"
        "不要编造隐藏测试，不要改文件。只输出一个 JSON 对象，字段为："
        "decision, reviewed_spec_version, required_spec_version, criterion_id, evidence, required_change。\n"
        f"【审查标准】{json.dumps(private, ensure_ascii=False)}\n"
        f"【草稿】\n{draft_source[:6000]}\n"
    )


def self_check_prompt(draft_source: str, private: dict[str, Any]) -> str:
    return (
        "你正在自检刚才写的代码。只能根据当前验收要求和草稿做决定。"
        "不要编造隐藏测试，这一步不要改文件。只输出一个 JSON 对象，字段为："
        "decision, reviewed_spec_version, required_spec_version, criterion_id, evidence, required_change。\n"
        f"【当前验收要求】{json.dumps(private, ensure_ascii=False)}\n"
        f"【草稿】\n{draft_source[:6000]}\n"
    )


def parse_review(text: str) -> dict[str, Any]:
    return parse_review_json(text)


def current_private(task: dict, variant: str) -> dict[str, Any]:
    return private_payload(task, "v1" if variant == "control" else "v2")
