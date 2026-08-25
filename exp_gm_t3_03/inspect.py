from __future__ import annotations

from typing import Any

from cal_gm_change_01.contract import KEEP, UPDATE
from exp_gm_t3_01.inspect import registered_value, unregistered_names, values_match
from exp_gm_t3_03.prompts import required_value
from gaworld.work.artifact_facts import values_equal


def apply_status(task: dict[str, Any], source: str, review: dict[str, Any] | None) -> dict[str, Any]:
    changes = list((review or {}).get("required_changes") or [])
    got = registered_value(source, task)
    adopted: list[str] = []
    missed: list[str] = []
    for change in changes:
        path = str(change.get("path") or "")
        if path != task["symbol"]:
            if values_equal(change.get("new_value"), _lookup(source, path)):
                adopted.append(path)
            else:
                missed.append(path)
            continue
        if values_match(got, change.get("new_value")):
            adopted.append(path)
        else:
            missed.append(path)
    extra = sorted(unregistered_names(source, task))
    return {
        "got": got,
        "required_n": len(changes),
        "adopted": adopted,
        "missed": missed,
        "adopted_n": len(adopted),
        "unregistered": bool(extra),
        "extra_names": extra,
        "complete": bool(review is not None) and not missed and not extra,
        "partial": bool(adopted) and bool(missed),
    }


def _lookup(source: str, path: str) -> Any:
    import re

    match = re.search(rf"^{re.escape(path)}\s*=\s*(.+)$", source or "", re.M)
    if not match:
        return None
    raw = match.group(1).strip().split("#")[0].strip().strip("\"'")
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return raw


def expected_review(task: dict[str, Any], variant: str, observed: Any) -> dict[str, Any]:
    required = required_value(task, variant)
    if values_match(observed, required):
        return {"decision": KEEP, "required_changes": []}
    return {
        "decision": UPDATE,
        "required_changes": [{"path": task["symbol"], "old_value": observed, "new_value": required}],
    }


def decision_correct(task: dict[str, Any], variant: str, review: dict[str, Any], observed: Any) -> bool:
    want = expected_review(task, variant, observed)
    if review.get("decision") != want["decision"]:
        return False
    if want["decision"] == KEEP:
        return not (review.get("required_changes") or [])
    got = review.get("required_changes") or []
    return any(
        item.get("path") == task["symbol"]
        and values_match(item.get("old_value"), observed)
        and values_match(item.get("new_value"), required_value(task, variant))
        for item in got
    )


def evidence_correct(task: dict[str, Any], variant: str, review: dict[str, Any], observed: Any) -> bool:
    evidence = review.get("evidence") or {}
    return (
        evidence.get("path") == task["symbol"]
        and values_match(evidence.get("observed"), observed)
        and values_match(evidence.get("required"), required_value(task, variant))
    )
