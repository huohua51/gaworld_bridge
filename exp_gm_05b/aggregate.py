from __future__ import annotations

from collections import defaultdict
from typing import Any


def _pass(cell: dict) -> int:
    extra = cell.get("extra") or {}
    if extra.get("track") == "direct_final_spec":
        return int(bool(extra.get("target_correct")))
    return int(bool(cell.get("full_pass")))


def paired_mean(cells: list[dict], left: str, right: str) -> float | None:
    groups: dict[tuple, dict] = defaultdict(dict)
    for cell in cells:
        extra = cell.get("extra") or {}
        if not cell.get("measurement_valid"):
            continue
        key = (extra.get("task_id"), extra.get("variant"), extra.get("repeat_id"))
        groups[key][extra.get("track")] = cell
    diffs = []
    for group in groups.values():
        if left in group and right in group:
            diffs.append(_pass(group[left]) - _pass(group[right]))
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


def target_correct_count(cells: list[dict]) -> tuple[int, int]:
    valid = [c for c in cells if c.get("measurement_valid")]
    hits = sum(int(bool((c.get("extra") or {}).get("target_correct"))) for c in valid)
    return hits, len(valid)


def direct_gate(cells: list[dict]) -> str:
    hits, n = target_correct_count(cells)
    if n != 6:
        return "invalid_matrix"
    if hits == 0:
        return "contract_or_task_broken"
    if hits <= 2:
        return "still_near_floor"
    if hits <= 5:
        return "intermediate_ok"
    return "maybe_too_easy"


def review_gate(cells: list[dict]) -> str:
    valid = [c for c in cells if c.get("measurement_valid")]
    if not valid or len(valid) < len(cells):
        return "A_r0"
    def mean(track: str) -> float:
        subset = [c for c in valid if (c.get("extra") or {}).get("track") == track]
        if not subset:
            return 0.0
        return sum(int(c.get("full_pass") or 0) for c in subset) / len(subset)
    s, m, d = mean("single"), mean("multi"), mean("drop")
    drop_i = [
        c for c in valid
        if (c.get("extra") or {}).get("track") == "drop" and (c.get("extra") or {}).get("variant") == "intervention"
    ]
    drop_i_rate = sum(int(c.get("full_pass") or 0) for c in drop_i) / len(drop_i) if drop_i else 0.0
    if s == 1.0 and m == 1.0 and d == 1.0:
        return "all_high_possible_leak"
    if s >= 0.5 and m >= 0.5 and drop_i_rate == 0:
        return "review_has_value_fill_repeats"
    if s >= 0.5 and m < 0.5:
        return "multi_negative_maybe_04f"
    if s < 0.5 and m >= 0.5 and drop_i_rate == 0:
        return "independent_reviewer_value"
    if s < 0.5 and m < 0.5:
        return "still_floor"
    if abs(m - d) < 1e-9:
        return "review_message_inert"
    return "mixed_inspect"


def na_if_floor(raw: float | None, floor: bool) -> str | float | None:
    if floor:
        return "N/A"
    return raw
