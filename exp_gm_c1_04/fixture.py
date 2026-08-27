"""Oracle fixture used only to calibrate the frozen C1-04 runner."""

from __future__ import annotations

import json
from typing import Any

from benchmark_core.model_runner import CallableModelClient
from exp_gm_c1_04.loader import RULE_ID, solve


def _handler(prompt: str, _task: str, _agent_id: str | None) -> str:
    payload: dict[str, Any] = json.loads(prompt)
    stage = payload["stage"]
    if stage == "private_report":
        private = payload["private_context"]
        response = {
            "agent_id": private["agent_id"],
            "feasible": private["feasible"],
            "preferred": private["preferred"],
        }
    elif stage == "coordinator_initial":
        spec = payload["registered_spec"]
        response = {
            "assignments": solve(spec["priority"], payload["delivered_reports"]),
            "rule": RULE_ID,
        }
    elif stage == "coordinator_retry":
        reports = payload["delivered_reports"]
        spec = payload["registered_spec"]
        protected = spec["protected_assignment"]
        protected_agent = protected["agent_id"]
        other = "agent_b" if protected_agent == "agent_a" else "agent_a"
        protected_slot = protected["slot"]
        other_slot = next(slot for slot in reports[other]["feasible"] if slot != protected_slot)
        response = {
            "assignments": {protected_agent: protected_slot, other: other_slot},
            "rule": RULE_ID,
        }
    elif stage == "agent_commit":
        plan = payload.get("delivered_platform_plan")
        agent_id = payload["role"]
        slot = (plan.get("assignments") or {}).get(agent_id) if plan else None
        response = {
            "agent_id": agent_id,
            "confirm": bool(slot and slot in payload["private_context"]["feasible"]),
            "slot": slot,
        }
    else:
        raise ValueError(f"unknown fixture stage: {stage}")
    return json.dumps(response, ensure_ascii=False, separators=(",", ":"))


def fixture_client() -> CallableModelClient:
    return CallableModelClient(
        _handler,
        provider="offline-c1-v4-oracle-fixture",
        model_version="offline-c1-v4-fixture",
        live=False,
    )
