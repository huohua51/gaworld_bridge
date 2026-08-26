"""Offline oracle-shaped fixture used only to calibrate model-runner wiring."""

from __future__ import annotations

import json

from benchmark_core.model_runner import CallableModelClient


def _handler(prompt: str, task: str, agent_id: str | None) -> str:
    payload = json.loads(prompt)
    family = payload.get("task_family")
    if family == "T4":
        role = payload.get("role")
        if role == "source":
            response = {"forward": True, "reason": "registered route"}
        elif role == "intermediate":
            response = {"accept": True, "forward": True, "reason": "adopt and relay"}
        elif role == "target":
            message = payload.get("message")
            if message:
                response = {
                    "accept": True,
                    "target_action": message["payload"]["target_action"],
                    "reason": "act on adopted evidence",
                }
            else:
                response = {
                    "accept": False,
                    "target_action": "keep_current",
                    "reason": "no message evidence",
                }
        else:
            response = {}
    elif family == "T5":
        policy = payload.get("active_policy")
        binding = bool(
            policy and policy.get("signal", {}).get("notice_type") == "binding_rule"
        )
        eligible = bool(policy and policy.get("eligible"))
        response = {
            "perceived": bool(policy),
            "action": (
                str(policy["signal"]["target_action"])
                if binding and eligible
                else "keep_current"
            ),
            "reason": "binding eligible policy"
            if binding and eligible
            else "no binding effect",
        }
    else:
        response = {}
    return json.dumps(response, ensure_ascii=False, separators=(",", ":"))


def oracle_fixture_client() -> CallableModelClient:
    return CallableModelClient(
        _handler,
        provider="offline-oracle-fixture",
        model_version="offline-oracle-fixture-v1",
        live=False,
    )


__all__ = ["oracle_fixture_client"]
