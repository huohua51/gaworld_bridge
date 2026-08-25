"""Protocol layer for 04d. Maps mismatches JSON onto the existing ReviewChannel."""

from __future__ import annotations

import json
import re
from typing import Any


def freeze_ok(decision: str, mismatches: list) -> bool:
    empty = not mismatches
    if empty:
        return decision == "approve"
    return decision == "revise"


def to_review_action(protocol: dict[str, Any], private: dict[str, Any]) -> dict[str, Any]:
    mismatches = list(protocol.get("mismatches") or [])
    decision = str(protocol.get("decision") or "")
    required = {}
    for item in mismatches:
        path = str(item.get("path") or "")
        if path and path != "SPEC_VERSION":
            required[path] = item.get("required_value")
    first = mismatches[0] if mismatches else {}
    return {
        "decision": decision if decision in {"approve", "revise"} else "revise",
        "reviewed_spec_version": str(protocol.get("reviewed_spec_version") or "v1"),
        "required_spec_version": str(private.get("spec_version") or "v2"),
        "criterion_id": str(first.get("criterion_id") or private.get("criterion_id") or ""),
        "evidence": json.dumps(mismatches, ensure_ascii=False) if mismatches else "no mismatches",
        "required_change": required,
        "_protocol": protocol,
        "_freeze_ok": freeze_ok(decision, mismatches),
        "_mismatches": mismatches,
    }


def parse_applied_patch_ids(source: str) -> list[str]:
    match = re.search(r"APPLIED_PATCH_IDS\s*=\s*(\[[^\]]*\])", source or "")
    if not match:
        return []
    try:
        payload = json.loads(match.group(1).replace("'", '"'))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [str(item) for item in payload]
    return []


def patch_ids_of(mismatches: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("patch_id")) for item in mismatches if item.get("patch_id")]
