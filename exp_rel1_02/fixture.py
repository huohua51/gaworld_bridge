"""Deterministic REL1-v2 runner calibration fixture."""

from __future__ import annotations

import json

from benchmark_core.model_runner import CallableModelClient


def _handler(prompt: str, _task: str, _agent_id: str | None) -> str:
    payload = json.loads(prompt)
    stage = payload["stage"]
    if stage == "observe":
        out = {"signals": payload["registered_current_signals"]}
    elif stage == "trust_update":
        history = payload["history_rows_in_order"]
        current = payload["current_signals"]
        if payload["phase"] == "update":
            rows = [history[-1]]
            row = rows[0]
            trusted = next(source for source, state in row["reports"].items() if state == row["outcome"])
        else:
            scores = {item["person_id"]: 0 for item in current}
            for row in history:
                for source, state in row["reports"].items():
                    scores[source] += int(state == row["outcome"])
            trusted = max(scores, key=scores.get)
            rows = [row for row in history if row["reports"][trusted] == row["outcome"]]
        state = next(item["reported_state"] for item in current if item["person_id"] == trusted)
        other = next(item["person_id"] for item in current if item["person_id"] != trusted)
        out = {
            "trusted_source_id": trusted,
            "trusted_state": state,
            "other_source_id": other,
            "evidence_row_ids": [row["row_id"] for row in rows],
        }
    elif stage == "dispatch":
        state = payload["delivered_trust_message"]["trusted_state"]
        out = {"selected_value": payload["state_to_value"][state]}
    else:
        raise ValueError(stage)
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def fixture_client() -> CallableModelClient:
    return CallableModelClient(
        _handler,
        provider="offline-rel1-v2-oracle-fixture",
        model_version="offline-rel1-v2-fixture",
        live=False,
    )
