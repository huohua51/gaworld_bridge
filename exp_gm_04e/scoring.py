"""R0 and rates for 04e-R."""

from __future__ import annotations

from typing import Any


def r0_ok(loop: dict[str, Any]) -> tuple[bool, str]:
    if not loop.get("source"):
        return False, "fixed draft missing"
    if loop.get("reviewer_calls", 0) < 1:
        return False, "reviewer was not called"
    if loop.get("reviewer_calls", 0) > 2:
        return False, f"reviewer calls={loop.get('reviewer_calls')}"
    return True, "ok"


def r0_executor(loop: dict[str, Any]) -> tuple[bool, str]:
    if not loop.get("before"):
        return False, "fixed draft missing"
    if loop.get("executor_calls", 0) != 1:
        return False, f"executor calls={loop.get('executor_calls')}"
    if not loop.get("patches"):
        return False, "no correct patch delivered"
    return True, "ok"


def rate(cells: list[dict], key: str, *, variant: str | None = None, protocol: str | None = None) -> float | None:
    subset = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if variant and extra.get("variant") != variant:
            continue
        if protocol and extra.get("protocol") != protocol:
            continue
        if not cell.get("measurement_valid"):
            continue
        subset.append(cell)
    if not subset:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(key))) for c in subset) / len(subset), 4)


def grounding_rate(cells: list[dict], *, protocol: str) -> float | None:
    subset = [
        c for c in cells
        if (c.get("extra") or {}).get("protocol") == protocol
        and c.get("measurement_valid")
        and (c.get("extra") or {}).get("review_parseable")
    ]
    if not subset:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get("grounded"))) for c in subset) / len(subset), 4)


def parse_rate(cells: list[dict], *, protocol: str) -> float | None:
    subset = [
        c for c in cells
        if (c.get("extra") or {}).get("protocol") == protocol and c.get("measurement_valid")
    ]
    if not subset:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get("review_parseable"))) for c in subset) / len(subset), 4)


def mean_calls(cells: list[dict], *, protocol: str) -> float | None:
    subset = [
        c for c in cells
        if (c.get("extra") or {}).get("protocol") == protocol and c.get("measurement_valid")
    ]
    if not subset:
        return None
    return round(sum(int((c.get("extra") or {}).get("reviewer_calls") or 0) for c in subset) / len(subset), 4)
