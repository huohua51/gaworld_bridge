"""Paired outcome and workflow estimands. Floor/ceiling → N/A."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _metric(cell: dict, kind: str) -> int:
    extra = cell.get("extra") or {}
    if kind == "target":
        return int(bool(extra.get("target_correct")))
    return int(bool(cell.get("full_pass")))


def paired_mean(cells: list[dict], left: str, right: str, kind: str) -> float | None:
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
            diffs.append(_metric(group[left], kind) - _metric(group[right], kind))
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
    if key == "full_pass":
        return round(sum(int(bool(c.get("full_pass"))) for c in subset) / len(subset), 4)
    if key == "coverage":
        return 1.0
    return round(sum(int(bool((c.get("extra") or {}).get(key))) for c in subset) / len(subset), 4)


def track_table(cells: list[dict]) -> dict[str, dict[str, float | None]]:
    rows = {}
    for track in ("single", "multi", "drop"):
        subset = [c for c in cells if (c.get("extra") or {}).get("track") == track]
        valid = [c for c in subset if c.get("measurement_valid")]
        ctrl = [c for c in valid if (c.get("extra") or {}).get("variant") == "control"]
        interv = [c for c in valid if (c.get("extra") or {}).get("variant") == "intervention"]
        fp = None
        if ctrl:
            fp = round(1 - sum(int(bool((c.get("extra") or {}).get("review_decision_correct"))) for c in ctrl) / len(ctrl), 4)
        va = None
        if interv:
            va = round(sum(int(bool((c.get("extra") or {}).get("verified_patch_adoption"))) for c in interv) / len(interv), 4)
        pairs = strict_pair([c for c in valid if (c.get("extra") or {}).get("track") == track])
        rows[track] = {
            "coverage": round(len(valid) / len(subset), 4) if subset else 0.0,
            "target_correct": rate(subset, "target_correct", track=track),
            "full_pass": rate(subset, "full_pass", track=track),
            "strict_pair": pairs,
            "false_positive_revision_rate": fp,
            "verified_patch_adoption_rate": va,
        }
    return rows


def strict_pair(cells: list[dict]) -> float | None:
    groups: dict[tuple, dict] = defaultdict(dict)
    for cell in cells:
        extra = cell.get("extra") or {}
        if not cell.get("measurement_valid"):
            continue
        key = (extra.get("task_id"), extra.get("track"), extra.get("repeat_id"))
        groups[key][extra.get("variant")] = cell
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    ok = 0
    for pair in pairs:
        if pair["control"].get("full_pass") == 1 and pair["intervention"].get("full_pass") == 1:
            ok += 1
    return round(ok / len(pairs), 4)


def first_error_hist(cells: list[dict]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for cell in cells:
        err = (cell.get("extra") or {}).get("first_error") or (cell.get("process_profile") or {}).get("first_error") or "unknown"
        hist[err] = hist.get(err, 0) + 1
    return hist


def repeat0_gate(cells: list[dict], *, rerun: bool = False) -> str:
    valid = [c for c in cells if c.get("measurement_valid")]
    if not cells or len(valid) < len(cells):
        return "A_r0_again" if rerun else "A_r0"
    def mean(track: str, kind: str) -> float:
        subset = [c for c in valid if (c.get("extra") or {}).get("track") == track]
        if not subset:
            return 0.0
        return sum(_metric(c, kind) for c in subset) / len(subset)
    s, m = mean("single", "full"), mean("multi", "full")
    if s == 1.0 and m == 1.0:
        return "B_ceiling"
    if s == 0.0 and m == 0.0:
        return "C_floor"
    return "D_difference"


def na_if_extreme(raw: float | None, gate: str) -> str | float | None:
    if gate in {"A_r0", "A_r0_again", "B_ceiling", "C_floor"}:
        return "N/A"
    return raw


def common_first_error(cells: list[dict]) -> str:
    hist = first_error_hist([c for c in cells if (c.get("extra") or {}).get("first_error") not in {None, "none"}])
    if not hist:
        return "none"
    return sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
