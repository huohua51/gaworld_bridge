"""Composed CHANGE-01 decision/evidence + APPLY-01 required_changes. No third protocol."""

from __future__ import annotations

from typing import Any

from cal_gm_change_01.contract import (
    CONTRACT_ACTION,
    DECISIONS,
    EVIDENCE_KEYS,
    KEEP,
    UPDATE,
    _evidence_ok,
    _present,
    parse_json_object,
)

CHANGE_KEYS = ("path", "old_value", "new_value")
CONTRACT_KEEP_EXTRA = "keep_carries_required_change"
CONTRACT_UPDATE_MISSING = "update_missing_required_change"


def _change_ok(change: Any) -> bool:
    if not isinstance(change, dict):
        return False
    return all(_present(change, key) for key in CHANGE_KEYS)


def canonicalize(payload: dict[str, Any]) -> dict[str, Any]:
    evidence = payload.get("evidence") or {}
    changes = payload.get("required_changes") or []
    out: dict[str, Any] = {
        "decision": payload.get("decision"),
        "evidence": {key: evidence.get(key) for key in EVIDENCE_KEYS},
        "required_changes": [],
    }
    if isinstance(changes, list):
        for index, item in enumerate(changes, start=1):
            if not isinstance(item, dict):
                continue
            row = {key: item.get(key) for key in CHANGE_KEYS}
            row["change_id"] = item.get("change_id") or f"change-{index:02d}"
            out["required_changes"].append(row)
    return out


def action_contract(payload: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if not isinstance(payload, dict) or not payload:
        return {}, "empty"
    if "decision" not in payload or "evidence" not in payload or "required_changes" not in payload:
        return dict(payload), "fields_not_extractable"
    if not _evidence_ok(payload.get("evidence")):
        return dict(payload), "fields_not_extractable"
    if not isinstance(payload.get("required_changes"), list):
        return dict(payload), "fields_not_extractable"
    name = payload.get("decision")
    if name not in DECISIONS:
        return dict(payload), CONTRACT_ACTION
    action = canonicalize(payload)
    if name == KEEP:
        if action["required_changes"]:
            return action, CONTRACT_KEEP_EXTRA
        return action, "ok"
    if not action["required_changes"] or not all(_change_ok(item) for item in action["required_changes"]):
        return action, CONTRACT_UPDATE_MISSING
    return action, "ok"
