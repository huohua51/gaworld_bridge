"""Deterministic review_action contract. No LLM judge, no Oracle backfill."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

DECISIONS = {"approve", "revise"}
RETRY_PREFIX = (
    "Your previous response did not satisfy the required JSON schema.\n"
    "Return only a valid review_action object.\n"
    "Do not reconsider the task or add explanations.\n"
)


@dataclass
class ContractResult:
    ok: bool
    action: dict[str, Any] | None
    error: str | None
    missing: list[str] = field(default_factory=list)
    parser_repair_used: bool = False
    contract_retry_used: bool = False
    contract_retry_success: bool = False
    total_review_calls: int = 1
    raw: str = ""
    retry_raw: str = ""
    problems: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "missing": list(self.missing),
            "parser_repair_used": self.parser_repair_used,
            "contract_retry_used": self.contract_retry_used,
            "contract_retry_success": self.contract_retry_success,
            "total_review_calls": self.total_review_calls,
            "problems": list(self.problems),
        }


def schema_prompt() -> str:
    return (
        "只输出一个 JSON 对象，不要 Markdown 围栏，不要散文。字段必须是：\n"
        '{"decision":"approve|revise","mismatches":[],"required_change":null}\n'
        "规则：approve 时 mismatches=[] 且 required_change=null。"
        "revise 时 mismatches 至少一项，且 required_change="
        '{"path":"<登记路径>","old_value":"<当前值>","new_value":"<要求值>"}。'
        "path、old_value、new_value 必须齐全。不要用散文代替结构化动作。\n"
    )


def _strip_fence(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw)
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return raw


def _trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _extract_objects(text: str) -> list[str]:
    objs: list[str] = []
    depth = 0
    start = None
    in_str = False
    escape = False
    for i, ch in enumerate(text or ""):
        if start is None:
            if ch == "{":
                start = i
                depth = 1
                in_str = False
                escape = False
            continue
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                objs.append(text[start : i + 1])
                start = None
    return objs


def _load_json(text: str) -> tuple[dict[str, Any] | None, bool]:
    raw = _strip_fence(text)
    repair = raw != (text or "").strip()
    candidates = [raw, _trailing_commas(raw)]
    for cand in candidates:
        try:
            payload = json.loads(cand)
            if isinstance(payload, dict):
                return payload, repair or cand != raw
        except json.JSONDecodeError:
            continue
    objs = _extract_objects(raw)
    if len(objs) != 1:
        return None, repair
    try:
        payload = json.loads(_trailing_commas(objs[0]))
    except json.JSONDecodeError:
        return None, True
    if not isinstance(payload, dict):
        return None, True
    return payload, True


def _looks_like_prose(text: str) -> bool:
    raw = _strip_fence(text)
    if not raw:
        return True
    if "{" not in raw:
        return True
    return False


def validate_action(payload: dict[str, Any]) -> ContractResult:
    missing = [k for k in ("decision", "mismatches", "required_change") if k not in payload]
    if missing:
        return ContractResult(False, None, "missing_fields", missing=missing, problems=[f"missing fields: {missing}"])
    decision = payload.get("decision")
    if decision not in DECISIONS:
        return ContractResult(
            False, None, "invalid_enum", problems=[f"decision not in {sorted(DECISIONS)}"]
        )
    mismatches = payload.get("mismatches")
    if not isinstance(mismatches, list):
        return ContractResult(False, None, "missing_fields", missing=["mismatches"], problems=["mismatches must be a list"])
    change = payload.get("required_change")
    if decision == "approve":
        if mismatches:
            return ContractResult(False, None, "approve_has_mismatch", problems=["approve must have mismatches=[]"])
        if change is not None:
            return ContractResult(False, None, "approve_has_change", problems=["approve must have required_change=null"])
        action = {"decision": "approve", "mismatches": [], "required_change": None}
        return ContractResult(True, action, None)
    if not mismatches:
        return ContractResult(False, None, "revise_missing_mismatch", problems=["revise must have at least one mismatch"])
    if not isinstance(change, dict):
        return ContractResult(False, None, "revise_missing_change", problems=["revise must have required_change object"])
    need = [k for k in ("path", "old_value", "new_value") if k not in change or change.get(k) is None]
    if need:
        return ContractResult(
            False, None, "revise_missing_change", missing=need, problems=[f"required_change missing {need}"]
        )
    for item in mismatches:
        if not isinstance(item, dict) or any(k not in item for k in ("path", "observed", "required")):
            return ContractResult(False, None, "missing_fields", missing=["mismatches.path|observed|required"], problems=["mismatch fields incomplete"])
    action = {
        "decision": "revise",
        "mismatches": [{"path": str(i["path"]), "observed": i["observed"], "required": i["required"]} for i in mismatches],
        "required_change": {
            "path": str(change["path"]),
            "old_value": change["old_value"],
            "new_value": change["new_value"],
        },
    }
    return ContractResult(True, action, None)


def parse_review_action(text: str) -> ContractResult:
    raw = text or ""
    payload, repaired = _load_json(raw)
    if payload is None:
        err = "prose_only" if _looks_like_prose(raw) else "json_unparseable"
        return ContractResult(False, None, err, parser_repair_used=repaired, raw=raw, problems=[err])
    result = validate_action(payload)
    result.parser_repair_used = repaired
    result.raw = raw
    return result


def retry_prompt(previous: ContractResult) -> str:
    bits = list(previous.problems) or [previous.error or "json_unparseable"]
    if previous.missing:
        bits.append("missing fields: " + ", ".join(previous.missing))
    return RETRY_PREFIX + "Problems: " + "; ".join(bits) + "\n"


def collect_review_action(call_llm: Callable[[str], str], first_prompt: str) -> ContractResult:
    first = call_llm(first_prompt)
    parsed = parse_review_action(first)
    parsed.total_review_calls = 1
    parsed.raw = first
    if parsed.ok:
        return parsed
    second = call_llm(retry_prompt(parsed))
    parsed2 = parse_review_action(second)
    parsed2.contract_retry_used = True
    parsed2.contract_retry_success = parsed2.ok
    parsed2.total_review_calls = 2
    parsed2.raw = first
    parsed2.retry_raw = second
    parsed2.parser_repair_used = parsed.parser_repair_used or parsed2.parser_repair_used
    if not parsed2.ok:
        second_err = parsed2.error
        parsed2.problems = [previous_error := (parsed.error or "first_fail"), second_err or "second_fail"]
        parsed2.error = "model_contract_failure"
        parsed2.missing = parsed2.missing or parsed.missing
    return parsed2


def channel_payload(action: dict[str, Any], *, draft_version: str, private: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    decision = action.get("decision")
    change = action.get("required_change")
    mapped: dict[str, Any] = {}
    if isinstance(change, dict) and "path" in change:
        mapped[str(change["path"])] = change.get("new_value")
    return {
        "decision": decision,
        "reviewed_spec_version": draft_version,
        "required_spec_version": str(private.get("spec_version") or draft_version),
        "criterion_id": criterion_id,
        "evidence": json.dumps(action.get("mismatches") or [], ensure_ascii=False),
        "required_change": mapped if decision == "revise" else {},
    }
