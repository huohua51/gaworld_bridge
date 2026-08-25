"""Read registered constants from an artifact. Oracle stays off-agent."""

from __future__ import annotations

import re
from typing import Any

from gaworld.work.artifact_facts import values_equal


def spec_version(source: str) -> str | None:
    match = re.search(r'SPEC_VERSION\s*=\s*["\'](v\d+)["\']', source or "")
    return match.group(1) if match else None


def registered_value(source: str, task: dict) -> Any:
    match = re.search(rf"^{re.escape(task['symbol'])}\s*=\s*(.+)$", source or "", re.M)
    if not match:
        return None
    raw = match.group(1).strip().split("#")[0].strip().strip("\"'")
    try:
        return int(float(raw)) if task["parse"] == "int" else float(raw)
    except (TypeError, ValueError):
        return raw


def top_level_names(source: str) -> set[str]:
    return set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=", source or "", re.M))


def unregistered_names(source: str, task: dict) -> set[str]:
    allowed = set(task.get("allow_names") or [])
    allowed.update({"APPLIED_PATCH_IDS", "ARTIFACT_SPEC_VERSION", "ARTIFACT_HASH_AFTER"})
    return top_level_names(source) - allowed


def declared_patch_ids(source: str) -> bool:
    return bool(re.search(r"APPLIED_PATCH_IDS\s*=", source or ""))


def values_match(got: Any, want: Any) -> bool:
    return values_equal(got, want)
