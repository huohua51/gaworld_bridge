"""Oracle fixture for T5-v3 repeat calibration only."""

from __future__ import annotations

import json

from benchmark_core.model_runner import CallableModelClient


def _handler(prompt: str, task: str, agent_id: str | None) -> str:
    payload = json.loads(prompt)
    context = payload["policy_context"]
    directive = payload["resident_directive"]
    response = {
        "notice_seen": bool(context["notice_present"]),
        "binding": bool(context["binding"]),
        "target_match": bool(directive["target_match"]),
        "authorized": bool(directive["authorized"]),
        "action": str(directive["action"]),
        "reason": "copy the sole registered resident directive",
    }
    return json.dumps(response, ensure_ascii=False, separators=(",", ":"))


def oracle_fixture_client() -> CallableModelClient:
    return CallableModelClient(
        _handler,
        provider="offline-t5-v3-scope-oracle-fixture",
        model_version="offline-t5-v3-scope-oracle-fixture-v1",
        live=False,
    )


__all__ = ["oracle_fixture_client"]
