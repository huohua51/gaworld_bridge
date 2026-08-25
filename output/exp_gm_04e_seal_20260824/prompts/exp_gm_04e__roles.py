"""Reviewer prompts for legacy vs evidence-bound protocols."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_04c.roles import parse_review_json
from exp_gm_04e.tasks import FACT_SPECS
from gaworld.work.artifact_facts import ArtifactFact, extract_facts, facts_to_public


def facts_for(task: dict, source: str) -> list[ArtifactFact]:
    return extract_facts(source, specs=FACT_SPECS[task["id"]], path="main.py")


def rule_reviewer(task: dict, source: str, private: dict[str, Any], *, protocol: str) -> dict[str, Any]:
    facts = facts_for(task, source)
    required = dict(private.get("required_change") or {})
    if protocol != "evidence_bound":
        from exp_gm_04c.roles import rule_reviewer as legacy

        return legacy(source, task, private)
    mismatches = []
    for fact in facts:
        want = required.get(fact.criterion_path)
        if want is None or _same(fact.observed_value, want):
            continue
        mismatches.append(
            {
                "criterion_id": private.get("criterion_id") or task["criterion_id"],
                "fact_id": fact.fact_id,
                "observed_value": fact.observed_value,
                "required_value": want,
                "operator": "equals",
            }
        )
    return {
        "decision": "approve" if not mismatches else "revise",
        "mismatches": mismatches,
    }


def _same(left: Any, right: Any) -> bool:
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return left == right


def evidence_prompt(source: str, facts: list[ArtifactFact], private: dict[str, Any], extra: str = "") -> str:
    payload = {
        "artifact_facts": facts_to_public(facts),
        "private_criterion": private,
    }
    if extra:
        payload["verifier_nack"] = extra
    return (
        "你是代码审核员。只能根据私有标准和本次草稿的只读事实做决定。不要改文件，不要编造 fact_id。\n"
        "只输出一个 JSON 对象，字段为 decision 与 mismatches。\n"
        "每条 mismatch 必须含 criterion_id, fact_id, observed_value, required_value, operator。\n"
        "operator 只能是 equals。事实已满足标准时必须 approve，且 mismatches 为空。\n"
        "mismatch 必须绑定本次提供的 fact_id，observed_value 必须等于该事实。\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
        f"【草稿】\n{source[:4000]}\n"
    )


def legacy_prompt(source: str, private: dict[str, Any], extra: str = "") -> str:
    note = f"\n【可再输出一次】{extra}\n" if extra else "\n"
    return (
        "你是代码审核员。只能根据登记的审查标准和草稿源码做决定。"
        "不要编造隐藏测试。只输出一个 JSON 对象，字段为："
        "decision, reviewed_spec_version, required_spec_version, criterion_id, evidence, required_change。"
        f"{note}"
        f"【审查标准】{json.dumps(private, ensure_ascii=False)}\n"
        f"【草稿】\n{source[:4000]}\n"
    )


def parse_review(text: str) -> dict[str, Any]:
    return parse_review_json(text)


def true_revision(review: dict[str, Any], task: dict, private: dict[str, Any], *, protocol: str, grounded: bool) -> bool:
    if review.get("decision") != "revise" or not grounded:
        return False
    required = dict(task["change_v2"] if str(private.get("spec_version")) == "v2" else task["change_v1"])
    if protocol != "evidence_bound":
        got = dict(review.get("required_change") or {})
        return review.get("required_spec_version") == "v2" and _same_change(got, required)
    covered = {}
    for item in review.get("mismatches") or []:
        # Map via required_value matching a registered key.
        for key, want in required.items():
            if _same(item.get("required_value"), want):
                covered[key] = item.get("required_value")
    return _same_change(covered, required)


def _same_change(got: dict, required: dict) -> bool:
    if set(got) != set(required):
        return False
    return all(_same(got[key], required[key]) for key in required)
