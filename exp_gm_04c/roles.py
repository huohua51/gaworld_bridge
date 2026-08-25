"""Rule roles for negative controls, plus LLM prompts for live cells."""

from __future__ import annotations

import json
import re
from typing import Any


_WAGE = '''SPEC_VERSION = "{version}"
THRESHOLD = {value}

def decide(take_home):
    return "accept" if take_home >= THRESHOLD else "reject"
'''

_RET = '''SPEC_VERSION = "{version}"
RATE = {value}

def min_return(principal):
    return int(principal * RATE)
'''

_BUDGET = '''SPEC_VERSION = "{version}"
BUDGET = {value}

def remaining(spent):
    return max(0, BUDGET - spent)
'''


def spec_from_version(task: dict, version: str) -> dict[str, Any]:
    change = dict(task["change_v1"] if version == "v1" else task["change_v2"])
    if task["id"] == "w1_wage_gate":
        return {"version": version, "value": change["reservation_wage"], "template": _WAGE}
    if task["id"] == "w1_return_floor":
        return {"version": version, "value": change["min_return_rate"], "template": _RET}
    return {"version": version, "value": change["total_budget"], "template": _BUDGET}


def render_source(task: dict, version: str) -> str:
    spec = spec_from_version(task, version)
    return spec["template"].format(version=spec["version"], value=spec["value"])


def inspect_draft(source: str, task: dict) -> dict[str, Any]:
    version = None
    match = re.search(r'SPEC_VERSION\s*=\s*["\'](v\d+)["\']', source or "")
    if match:
        version = match.group(1)
    observed: dict[str, Any] = {}
    if task["id"] == "w1_wage_gate":
        num = re.search(r"(?:THRESHOLD|reservation_wage)\s*=\s*(\d+)", source or "")
        if num:
            observed["reservation_wage"] = int(num.group(1))
    elif task["id"] == "w1_return_floor":
        num = re.search(r"(?:RATE|min_return_rate)\s*=\s*([0-9.]+)", source or "")
        if num:
            observed["min_return_rate"] = float(num.group(1))
    else:
        if task.get("const") and task.get("path"):
            num = re.search(
                rf"(?:{re.escape(str(task['const']))}|{re.escape(str(task['path']))})\s*=\s*([0-9.]+)",
                source or "",
            )
            if num:
                raw = num.group(1)
                observed[task["path"]] = int(raw) if "." not in raw else float(raw)
        else:
            num = re.search(r"(?:BUDGET|total_budget|THRESHOLD)\s*=\s*(\d+)", source or "")
            if num:
                observed["total_budget"] = int(num.group(1))
    return {"spec_version": version, "observed": observed}


def rule_reviewer(draft_source: str, task: dict, private: dict[str, Any]) -> dict[str, Any]:
    inspect = inspect_draft(draft_source, task)
    required = dict(private.get("required_change") or {})
    required_version = str(private.get("spec_version", "v1"))
    matches = inspect["spec_version"] == required_version and inspect["observed"] == required
    if matches:
        return {
            "decision": "approve",
            "reviewed_spec_version": inspect["spec_version"] or "v1",
            "required_spec_version": required_version,
            "criterion_id": private.get("criterion_id") or task["criterion_id"],
            "evidence": f"draft already matches {required_version}",
            "required_change": {},
        }
    return {
        "decision": "revise",
        "reviewed_spec_version": inspect["spec_version"] or "v1",
        "required_spec_version": required_version,
        "criterion_id": private.get("criterion_id") or task["criterion_id"],
        "evidence": f"draft={inspect['observed']} required={required}",
        "required_change": required,
    }


def rule_executor(task: dict, *, version: str, review: dict[str, Any] | None = None) -> str:
    if review and review.get("decision") == "revise" and review.get("required_change"):
        required_version = str(review.get("required_spec_version") or "v2")
        return render_source(task, required_version)
    return render_source(task, version)


def parse_review_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw)
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            payload = json.loads(match.group(0))
            if isinstance(payload, dict):
                return payload
    raise ValueError("reviewer output is not a JSON object")


def executor_prompt(brief_text: str, review: dict[str, Any] | None = None) -> str:
    extra = ""
    if review:
        extra = (
            "\n【审核意见】必须采用下面这条已送达的审核，按 required_change 重写，"
            "并更新 SPEC_VERSION。\n"
            + json.dumps(review, ensure_ascii=False)
        )
    return brief_text + extra


def reviewer_prompt(draft_source: str, private: dict[str, Any]) -> str:
    return (
        "你是代码审核员。只能根据登记的审查标准和草稿源码做决定。"
        "不要编造隐藏测试。只输出一个 JSON 对象，字段为："
        "decision, reviewed_spec_version, required_spec_version, criterion_id, evidence, required_change。\n"
        f"【审查标准】{json.dumps(private, ensure_ascii=False)}\n"
        f"【草稿】\n{draft_source[:4000]}\n"
    )


def expected_review_decision(variant: str) -> str:
    return "approve" if variant == "control" else "revise"
