"""Typed-patch construction and Executor prompts. Reviewer is Rule-only here."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_04c.roles import executor_prompt as legacy_executor_prompt
from exp_gm_04c.roles import render_source, rule_reviewer as legacy_rule_reviewer
from exp_gm_04e.roles import facts_for
from exp_gm_04e.tasks import FACT_SPECS, private_payload
from gaworld.work.artifact_facts import artifact_hash, values_equal


def typed_patches(task: dict, source: str) -> list[dict[str, Any]]:
    private = private_payload(task, "v2", protocol="evidence_bound")
    required = dict(private.get("required_change") or {})
    hashed = artifact_hash(source)
    patches: list[dict[str, Any]] = []
    index = 1
    for fact in facts_for(task, source):
        if fact.criterion_path == "spec_version":
            continue
        want = required.get(fact.criterion_path)
        if want is None or values_equal(fact.observed_value, want):
            continue
        patches.append(
            {
                "patch_id": f"patch-{index:02d}",
                "path": fact.criterion_path,
                "observed_value": fact.observed_value,
                "required_value": want,
                "artifact_hash_before": hashed,
            }
        )
        index += 1
    return patches


def legacy_review(task: dict, source: str) -> dict[str, Any]:
    private = private_payload(task, "v2", protocol="legacy")
    return legacy_rule_reviewer(source, task, private)


def rule_executor(task: dict, *, protocol: str, source: str) -> str:
    rewritten = render_source(task, "v2")
    if protocol != "evidence_bound":
        return rewritten
    patches = typed_patches(task, source)
    ids = [item["patch_id"] for item in patches]
    extra = ""
    if ids:
        extra = (
            f'\nAPPLIED_PATCH_IDS = {json.dumps(ids)}\n'
            f'ARTIFACT_SPEC_VERSION = "v2"\n'
        )
    return rewritten.rstrip() + extra + "\n"


def executor_prompt(task: dict, source: str, *, protocol: str) -> str:
    brief = task["v1"]["brief"]
    if protocol != "evidence_bound":
        return (
            brief
            + "\n【当前草稿】必须从这份草稿改，不要从零编造无关文件。\n"
            + source
            + "\n"
            + legacy_executor_prompt("", legacy_review(task, source)).lstrip()
        )
    payload = {
        "patches": typed_patches(task, source),
        "instruction": (
            "按每条 patch 把草稿里的对应常量改成 required_value。"
            "不能只改 SPEC_VERSION。环境不会替你改文件。"
            "完成后在模块顶层写 APPLIED_PATCH_IDS 与 ARTIFACT_SPEC_VERSION。"
        ),
    }
    return (
        brief
        + "\n你是执行者。只根据已确认正确的 typed patch 修改当前草稿。\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\n【当前草稿】\n"
        + source
        + "\n只输出完整 Python 源码。\n"
    )
