"""Paired multi-agent metrics. Do not add them into one total."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _fp(cell: dict[str, Any]) -> int:
    extra = cell.get("extra") or {}
    if extra.get("track") == "drop":
        return int(bool(cell.get("full_pass")))
    return int(bool(cell.get("full_pass")))


def paired_mean(cells: list[dict], left: str, right: str) -> float | None:
    by_key: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for cell in cells:
        extra = cell.get("extra") or {}
        if not cell.get("measurement_valid"):
            continue
        key = (extra.get("task_id"), extra.get("variant"), extra.get("repeat_id"))
        by_key[key][extra.get("track")] = cell
    diffs = []
    for group in by_key.values():
        if left in group and right in group:
            diffs.append(_fp(group[left]) - _fp(group[right]))
    if not diffs:
        return None
    return round(sum(diffs) / len(diffs), 4)


def rate(cells: list[dict], key: str, **filters) -> float | None:
    subset = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if filters.get("variant") and extra.get("variant") != filters["variant"]:
            continue
        if filters.get("track") and extra.get("track") != filters["track"]:
            continue
        if not cell.get("measurement_valid"):
            continue
        subset.append(cell)
    if not subset:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(key))) for c in subset) / len(subset), 4)


def first_error_hist(cells: list[dict]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for cell in cells:
        err = (cell.get("process_profile") or {}).get("first_error") or "unknown"
        hist[err] = hist.get(err, 0) + 1
    return hist


def repeat0_gate(cells: list[dict]) -> str:
    valid = [c for c in cells if c.get("measurement_valid")]
    coverage = len(valid) / len(cells) if cells else 0.0
    if coverage < 1.0:
        return "A_r0_or_coverage"
    singles = [c for c in valid if (c.get("extra") or {}).get("track") == "single"]
    multis = [c for c in valid if (c.get("extra") or {}).get("track") == "multi"]
    if not singles or not multis:
        return "A_r0_or_coverage"
    s = sum(int(c.get("full_pass") or 0) for c in singles) / len(singles)
    m = sum(int(c.get("full_pass") or 0) for c in multis) / len(multis)
    if s == 1.0 and m == 1.0:
        return "B_ceiling"
    if s == 0.0 and m == 0.0:
        return "C_floor"
    return "D_difference"


def summarize(cells: list[dict]) -> dict[str, Any]:
    return {
        "requested": len(cells),
        "measurement_valid": sum(int(bool(c.get("measurement_valid"))) for c in cells),
        "coverage": round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4) if cells else 0,
        "multi_agent_net_benefit": paired_mean(cells, "multi", "single"),
        "review_causal_value": paired_mean(cells, "multi", "drop"),
        "false_positive_revision_rate": rate(cells, "review_decision_correct", variant="control"),
        "true_revision_rate": rate(cells, "review_decision_correct", variant="intervention"),
        "verified_patch_adoption_rate": rate(cells, "verified_patch_adoption", variant="intervention"),
        "declared_patch_adoption_rate": rate(cells, "declared_patch_adoption", variant="intervention"),
        "unregistered_change_rate": rate(cells, "unregistered_change"),
        "first_error": first_error_hist(cells),
        "repeat0_gate": repeat0_gate(cells),
    }
