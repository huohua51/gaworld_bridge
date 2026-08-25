"""required_change prompts. Hidden tests never enter prompts. No typed-patch."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_05b.artifacts import render_source
from exp_gm_05b.tasks import private_payload
from exp_gm_05c.contract import schema_prompt
from exp_gm_05c.inspect import registered_value, spec_version, values_match


def rule_builder_draft(task: dict) -> str:
    return render_source(task, "v1")


def rule_builder_revise(task: dict, *, review: dict[str, Any] | None, current: str) -> str:
    if not review or review.get("decision") != "revise":
        return current
    change = review.get("required_change")
    if not change:
        return current
    new_value = change.get("new_value") if isinstance(change, dict) else None
    if new_value is None and isinstance(change, dict):
        new_value = change.get(task["path"])
    if values_match(new_value, task["change_v2"][task["path"]]):
        return render_source(task, "v2")
    return current


def rule_reviewer(draft: str, task: dict, private: dict[str, Any]) -> dict[str, Any]:
    required = dict(private.get("required_change") or {})
    required_version = str(private.get("spec_version") or "v1")
    got = registered_value(draft, task)
    want = required.get(task["path"])
    version = spec_version(draft) or "v1"
    matches = version == required_version and values_match(got, want)
    if matches:
        return {"decision": "approve", "mismatches": [], "required_change": None}
    return {
        "decision": "revise",
        "mismatches": [{"path": task["path"], "observed": got, "required": want}],
        "required_change": {"path": task["path"], "old_value": got, "new_value": want},
    }


def builder_draft_prompt(brief: str) -> str:
    return brief + "\n只输出完整 Python 源码。\n"


def builder_revise_prompt(brief: str, source: str, review: dict[str, Any] | None) -> str:
    extra = "\n【当前草稿】从这份草稿修改或确认。环境不会替你改文件。\n" + source[:4000]
    if review:
        extra += (
            "\n【审核意见】按 required_change 修改真实常量并更新 SPEC_VERSION。"
            "required_change 含 path、old_value、new_value。把 old_value 改成 new_value。"
            "不要只改版本号，不要只写 APPLIED_PATCH_IDS。\n"
            + json.dumps(review, ensure_ascii=False)
        )
    return brief + extra + "\n只输出完整 Python 源码。\n"


def reviewer_prompt(draft: str, private: dict[str, Any]) -> str:
    return (
        "你是代码审核员。只能根据登记标准和草稿做决定。不要改文件，不要编造隐藏测试。\n"
        + schema_prompt()
        + f"【审查标准】{json.dumps(private, ensure_ascii=False)}\n【草稿】\n{draft[:4000]}\n"
    )


def self_check_prompt(draft: str, private: dict[str, Any]) -> str:
    return (
        "你正在自检刚才写的代码。只能根据当前验收要求和草稿做决定。"
        "不要编造隐藏测试，这一步不要改文件。\n"
        + schema_prompt()
        + f"【当前验收要求】{json.dumps(private, ensure_ascii=False)}\n【草稿】\n{draft[:4000]}\n"
    )


def current_private(task: dict, variant: str) -> dict[str, Any]:
    return private_payload(task, "v1" if variant == "control" else "v2")
