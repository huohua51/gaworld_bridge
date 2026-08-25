"""04d protocol roles. Prompt templates are task-agnostic."""

from __future__ import annotations

import json
import re
from typing import Any

from exp_gm_04c.roles import inspect_draft as inspect_dev
from exp_gm_04c.roles import parse_review_json, rule_executor as rule_executor_legacy
from exp_gm_04d.protocol import parse_applied_patch_ids, to_review_action


def inspect_draft(source: str, task: dict) -> dict[str, Any]:
    if task.get("split") != "held_out":
        return inspect_dev(source, task)
    version = None
    match = re.search(r'SPEC_VERSION\s*=\s*["\'](v\d+)["\']', source or "")
    if match:
        version = match.group(1)
    observed: dict[str, Any] = {}
    const = task["const"]
    path = task["path"]
    num = re.search(rf"(?:{re.escape(const)}|{re.escape(path)})\s*=\s*([0-9.]+)", source or "")
    if num:
        raw = num.group(1)
        observed[path] = int(raw) if task.get("parse") == "int" else float(raw)
    return {"spec_version": version, "observed": observed, "applied_patch_ids": parse_applied_patch_ids(source or "")}


def render_held_out(task: dict, version: str) -> str:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    value = change[task["path"]]
    return task["template"].format(version=version, value=value)


def rule_reviewer(draft_source: str, task: dict, private: dict[str, Any]) -> dict[str, Any]:
    inspect = inspect_draft(draft_source, task)
    required = dict(private.get("required_change") or {})
    required_version = str(private.get("spec_version", "v1"))
    mismatches: list[dict[str, Any]] = []
    idx = 1
    if inspect.get("spec_version") != required_version:
        mismatches.append(
            {
                "patch_id": f"patch-{idx:02d}",
                "criterion_id": private.get("criterion_id") or task["criterion_id"],
                "path": "SPEC_VERSION",
                "observed_value": inspect.get("spec_version"),
                "required_value": required_version,
                "evidence": "spec version differs",
            }
        )
        idx += 1
    for path, want in required.items():
        got = (inspect.get("observed") or {}).get(path)
        if got != want:
            mismatches.append(
                {
                    "patch_id": f"patch-{idx:02d}",
                    "criterion_id": private.get("criterion_id") or task["criterion_id"],
                    "path": path,
                    "observed_value": got,
                    "required_value": want,
                    "evidence": f"observed {got} required {want}",
                }
            )
            idx += 1
    protocol = {
        "decision": "approve" if not mismatches else "revise",
        "mismatches": mismatches,
        "reviewed_spec_version": inspect.get("spec_version") or "v1",
    }
    return to_review_action(protocol, private)


def rule_executor(task: dict, *, version: str, review: dict[str, Any] | None = None) -> str:
    if task.get("split") == "held_out":
        if review and review.get("decision") == "revise" and review.get("required_change"):
            source = render_held_out(task, str(review.get("required_spec_version") or "v2"))
            ids = [str(item.get("patch_id")) for item in (review.get("_mismatches") or []) if item.get("patch_id")]
            if ids:
                source = source.rstrip() + f"\nAPPLIED_PATCH_IDS = {json.dumps(ids)}\n"
            return source
        return render_held_out(task, version)
    source = rule_executor_legacy(task, version=version, review=review)
    if review and review.get("decision") == "revise":
        ids = [str(item.get("patch_id")) for item in (review.get("_mismatches") or []) if item.get("patch_id")]
        if ids and "APPLIED_PATCH_IDS" not in source:
            source = source.rstrip() + f"\nAPPLIED_PATCH_IDS = {json.dumps(ids)}\n"
    return source


def reviewer_prompt(draft_source: str, private: dict[str, Any]) -> str:
    return (
        "你是代码审核员。只能根据登记标准和草稿源码做决定。不要编造隐藏测试，不要改文件。\n"
        "只输出一个 JSON 对象，字段为 decision, mismatches, reviewed_spec_version。\n"
        "冻结规则：mismatches 为空则只能 decision=approve；mismatches 非空则只能 decision=revise。\n"
        "每条 mismatch 含 patch_id, criterion_id, path, observed_value, required_value, evidence。\n"
        f"【审查标准】{json.dumps(private, ensure_ascii=False)}\n"
        f"【草稿】\n{draft_source[:4000]}\n"
    )


def executor_prompt(brief_text: str, review: dict[str, Any] | None = None) -> str:
    extra = ""
    if review:
        protocol = review.get("_protocol") or {
            "decision": review.get("decision"),
            "mismatches": review.get("_mismatches") or [],
            "reviewed_spec_version": review.get("reviewed_spec_version"),
        }
        extra = (
            "\n【审核意见】必须采用下面已送达的审核。环境不会替你改文件。\n"
            "若 decision=approve，保持草稿。\n"
            "若 decision=revise，按 mismatches 里每条 required_value 改代码，更新 SPEC_VERSION，"
            "并在模块顶层写 APPLIED_PATCH_IDS = [\"patch-01\", ...]。不要只改版本号。\n"
            + json.dumps(protocol, ensure_ascii=False)
        )
    return brief_text + extra


def wrap_reviewer_output(raw: dict[str, Any], private: dict[str, Any]) -> dict[str, Any]:
    if "mismatches" in raw or "decision" in raw:
        return to_review_action(raw, private)
    return raw
