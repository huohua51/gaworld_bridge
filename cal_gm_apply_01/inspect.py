from __future__ import annotations

import re
from typing import Any

from gaworld.work.artifact_facts import extract_facts, values_equal
from gaworld.work.artifact_patches import parse_executor_claim

from cal_gm_apply_01.loader import fact_specs, required_changes


def parse_source(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", raw)
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return raw if raw.endswith("\n") else raw + "\n"


def read_values(source: str, task: dict[str, Any]) -> dict[str, Any]:
    facts = extract_facts(source or "", specs=fact_specs(task))
    return {item.criterion_path: item.observed_value for item in facts}


def top_level_names(source: str) -> set[str]:
    return set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=", source or "", re.M))


def unregistered_names(source: str, task: dict[str, Any]) -> set[str]:
    allowed = set(task.get("allow_names") or []) | {"APPLIED_PATCH_IDS", "ARTIFACT_SPEC_VERSION"}
    return top_level_names(source) - allowed


def declared_applied(source: str) -> bool:
    claim = parse_executor_claim(source)
    return bool(claim.get("applied_patch_ids")) or bool(re.search(r"APPLIED_PATCH_IDS\s*=", source or ""))


def field_status(task: dict[str, Any], variant: str, source: str) -> dict[str, Any]:
    got = read_values(source, task)
    required = required_changes(task, variant)
    adopted: list[str] = []
    missed: list[str] = []
    for change in required:
        path = change["path"]
        if values_equal(got.get(path), change["new_value"]):
            adopted.append(path)
        else:
            missed.append(path)
    extra_registered: list[str] = []
    required_paths = {item["path"] for item in required}
    for path, value in got.items():
        if path in required_paths:
            continue
        if values_equal(value, int(task["required"])):
            extra_registered.append(path)
        elif not values_equal(value, int(task["current"])):
            extra_registered.append(path)
    extra_names = sorted(unregistered_names(source, task))
    return {
        "got": got,
        "required_n": len(required),
        "adopted": adopted,
        "missed": missed,
        "adopted_n": len(adopted),
        "extra_registered": extra_registered,
        "extra_names": extra_names,
        "unregistered": bool(extra_names or extra_registered),
        "complete": bool(required) and not missed and not extra_names and not extra_registered,
        "partial": bool(adopted) and bool(missed),
        "declared": declared_applied(source),
    }
