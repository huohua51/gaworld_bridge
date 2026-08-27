"""Deterministic REL1-v3 calibration fixture."""

from __future__ import annotations

import json

from benchmark_core.model_runner import CallableModelClient


def _handler(prompt: str, _task: str, _agent_id: str | None) -> str:
    payload = json.loads(prompt)
    stage = payload["stage"]
    if stage == "observe":
        out = {"signals": payload["registered_current_signals"]}
    elif stage == "formation_count":
        history = payload["history_rows"]
        signals = payload["current_signals"]
        people = [item["person_id"] for item in signals]
        counts = {person: 0 for person in people}
        support = {person: [] for person in people}
        for row in history:
            for person in people:
                if row["reports"][person] == row["outcome"]:
                    counts[person] += 1
                    support[person].append(row["row_id"])
        trusted = max(counts, key=counts.get)
        out = {
            "correct_counts": counts,
            "supporting_row_ids": support,
            "trusted_source_id": trusted,
            "trusted_state": next(item["reported_state"] for item in signals if item["person_id"] == trusted),
            "other_source_id": next(person for person in people if person != trusted),
        }
    elif stage == "latest_binding_update":
        row = payload["history_rows_in_order"][-1]
        signals = payload["current_signals"]
        trusted = next(person for person, state in row["reports"].items() if state == row["outcome"])
        out = {
            "trusted_source_id": trusted,
            "trusted_state": next(item["reported_state"] for item in signals if item["person_id"] == trusted),
            "other_source_id": next(item["person_id"] for item in signals if item["person_id"] != trusted),
            "evidence_row_ids": [row["row_id"]],
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
        provider="offline-rel1-v3-oracle-fixture",
        model_version="offline-rel1-v3-fixture",
        live=False,
    )
