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
        return int(float(raw))
    except (TypeError, ValueError):
        return raw


def unregistered_names(source: str, task: dict) -> set[str]:
    names = set(re.findall(r"^([A-Z_][A-Z0-9_]*)\s*=", source or "", re.M))
    allowed = set(task.get("allow_names") or []) | {"APPLIED_PATCH_IDS", "ARTIFACT_SPEC_VERSION"}
    return names - allowed


def declared_patch(source: str) -> bool:
    return bool(re.search(r"APPLIED_PATCH_IDS\s*=", source or ""))


def values_match(left: Any, right: Any) -> bool:
    return values_equal(left, right)
