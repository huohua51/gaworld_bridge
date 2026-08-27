"""Deterministic C1-05 runner calibration fixture."""

from __future__ import annotations

import json

from benchmark_core.model_runner import CallableModelClient
from exp_gm_c1_05.loader import RULE_ID, solve


def _handler(prompt: str, _task: str, _agent_id: str | None) -> str:
    payload = json.loads(prompt)
    stage = payload["stage"]
    if stage == "private_report":
        private = payload["private_context"]
        out = {key: private[key] for key in ("agent_id", "feasible", "preferred")}
    elif stage == "coordinator_initial":
        out = {
            "assignments": solve(payload["phase1_spec"]["priority"], payload["delivered_reports"]),
            "rule": RULE_ID,
        }
    elif stage == "coordinator_retry":
        reports = payload["delivered_reports"]
        protected = payload["authoritative_current_spec"]["protected_assignment"]
        protected_agent = protected["agent_id"]
        protected_slot = protected["slot"]
        other = "agent_b" if protected_agent == "agent_a" else "agent_a"
        out = {
            "assignments": {
                protected_agent: protected_slot,
                other: next(slot for slot in reports[other]["feasible"] if slot != protected_slot),
            },
            "rule": RULE_ID,
        }
    elif stage == "agent_commit":
        plan = payload.get("delivered_platform_plan")
        agent = payload["role"]
        slot = (plan.get("assignments") or {}).get(agent) if plan else None
        out = {"agent_id": agent, "confirm": bool(slot), "slot": slot}
    else:
        raise ValueError(stage)
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


def fixture_client() -> CallableModelClient:
    return CallableModelClient(
        _handler,
        provider="offline-c1-v5-oracle-fixture",
        model_version="offline-c1-v5-fixture",
        live=False,
    )
