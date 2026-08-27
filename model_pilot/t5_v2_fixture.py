"""Oracle-shaped fixture for T5-v2 model-runner calibration only."""

from __future__ import annotations

import json

from benchmark_core.model_runner import CallableModelClient


def _handler(prompt: str, task: str, agent_id: str | None) -> str:
    payload = json.loads(prompt)
    state = payload["registered_policy_state"]
    status = str(state["status"])
    response = {
        "notice_seen": status != "absence",
        "binding": status == "binding",
        "action": str(state["required_action"]),
        "reason": "follow explicit registered policy state",
    }
    return json.dumps(response, ensure_ascii=False, separators=(",", ":"))


def oracle_fixture_client() -> CallableModelClient:
    return CallableModelClient(
        _handler,
        provider="offline-t5-v2-oracle-fixture",
        model_version="offline-t5-v2-oracle-fixture-v1",
        live=False,
    )


__all__ = ["oracle_fixture_client"]
