"""Oracle-shaped clients for expanded T5-v3 three-model calibration."""

from __future__ import annotations

import json

from benchmark_core.model_runner import CallableModelClient


def _handler(prompt: str, task: str, agent_id: str | None) -> str:
    payload = json.loads(prompt)
    context = payload["policy_context"]
    directive = payload["resident_directive"]
    return json.dumps(
        {
            "notice_seen": bool(context["notice_present"]),
            "binding": bool(context["binding"]),
            "target_match": bool(directive["target_match"]),
            "authorized": bool(directive["authorized"]),
            "action": str(directive["action"]),
            "reason": "follow expanded sealed resident directive",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def oracle_fixture_clients() -> dict[str, CallableModelClient]:
    return {
        "glm52": CallableModelClient(
            _handler,
            provider="offline-paratera-fixture",
            model_version="offline-GLM-5.2-fixture",
            live=False,
        ),
        "gpt54": CallableModelClient(
            _handler,
            provider="offline-qweapi-fixture",
            model_version="offline-gpt-5.4-fixture",
            live=False,
        ),
        "qwen37plus": CallableModelClient(
            _handler,
            provider="offline-qweapi-fixture",
            model_version="offline-qwen3.7-plus-fixture",
            live=False,
        ),
    }


__all__ = ["oracle_fixture_clients"]
