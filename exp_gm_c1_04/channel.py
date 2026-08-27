"""Typed delivery boundary for C1-04.

The validator owns plan identifiers. This channel only delivers an accepted,
platform-stamped plan and records agent claims that the registry confirmed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


class CoordinationDeliveryChannel:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._private: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._inbox: dict[str, dict[str, Any]] = {}
        self._plan: dict[str, Any] | None = None
        self._claims: dict[str, str] = {}
        self._denials: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def _append(self, event: dict[str, Any]) -> None:
        self.events.append(copy.deepcopy(event))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _deny(self, reason: str, **extra: Any) -> dict[str, Any]:
        payload = {"ok": False, "reason": reason, **extra}
        self._denials.append(payload)
        self._append({"event": "denied", **payload})
        return payload

    def put_private(self, owner: str, payload: dict[str, Any]) -> dict[str, Any]:
        if owner not in {"agent_a", "agent_b"}:
            return self._deny("invalid_private_owner", owner=owner)
        self._private[owner] = copy.deepcopy(payload)
        self._append({"event": "private_put", "owner": owner})
        return {"ok": True}

    def read_private(self, reader: str, owner: str) -> dict[str, Any]:
        if reader != owner:
            return self._deny("unauthorized_private_read", reader=reader, owner=owner)
        body = self._private.get(owner)
        if body is None:
            return self._deny("private_missing", owner=owner)
        self._append({"event": "private_read", "owner": owner})
        return {"ok": True, "payload": copy.deepcopy(body)}

    def emit_report(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if agent_id not in {"agent_a", "agent_b"}:
            return self._deny("invalid_reporter", agent_id=agent_id)
        self._reports[agent_id] = copy.deepcopy(payload)
        self._append({"event": "report_emitted", "agent_id": agent_id})
        return {"ok": True}

    def deliver_report(self, agent_id: str) -> dict[str, Any]:
        if agent_id not in self._reports:
            return self._deny("report_missing", agent_id=agent_id)
        self._inbox[agent_id] = copy.deepcopy(self._reports[agent_id])
        self._append({"event": "report_delivered", "agent_id": agent_id})
        return {"ok": True}

    def read_reports(self, reader: str) -> dict[str, Any]:
        if reader != "coordinator":
            return self._deny("unauthorized_report_read", reader=reader)
        self._append({"event": "reports_read", "reader": reader})
        return {"ok": True, "reports": copy.deepcopy(self._inbox)}

    def deliver_accepted_plan(self, plan: dict[str, Any] | None, *, drop: bool = False) -> dict[str, Any]:
        required = {"plan_id", "spec_version", "assignments"}
        if not isinstance(plan, dict) or not required.issubset(plan):
            return self._deny("accepted_platform_plan_required")
        if drop:
            self._append({"event": "accepted_plan_dropped", "plan_id": plan["plan_id"]})
            return {"ok": True, "dropped": True}
        self._plan = copy.deepcopy(plan)
        self._append(
            {
                "event": "accepted_plan_delivered",
                "plan_id": plan["plan_id"],
                "spec_version": plan["spec_version"],
            }
        )
        return {"ok": True, "dropped": False}

    def read_plan(self, reader: str) -> dict[str, Any]:
        if reader not in {"agent_a", "agent_b"}:
            return self._deny("unauthorized_plan_read", reader=reader)
        if self._plan is None:
            return self._deny("plan_not_delivered", reader=reader)
        self._append({"event": "accepted_plan_read", "reader": reader})
        return {"ok": True, "plan": copy.deepcopy(self._plan)}

    def submit_confirmed_claim(
        self,
        *,
        role: str,
        agent_id: str,
        slot: str,
        plan_id: str,
        registry_confirmation: dict[str, Any],
    ) -> dict[str, Any]:
        if role not in {"agent_a", "agent_b"} or role != agent_id:
            return self._deny("unauthorized_world_write", role=role, agent_id=agent_id)
        if not registry_confirmation.get("ok"):
            return self._deny("registry_confirmation_required", agent_id=agent_id)
        if self._plan is None or plan_id != self._plan.get("plan_id"):
            return self._deny("undelivered_plan_id", agent_id=agent_id)
        if slot != (self._plan.get("assignments") or {}).get(agent_id):
            return self._deny("claim_slot_mismatch", agent_id=agent_id)
        self._claims[agent_id] = slot
        self._append(
            {"event": "confirmed_claim", "agent_id": agent_id, "slot": slot, "plan_id": plan_id}
        )
        return {"ok": True}

    def world_state(self) -> dict[str, Any]:
        occupied: dict[str, list[str]] = {}
        for agent_id, slot in self._claims.items():
            occupied.setdefault(slot, []).append(agent_id)
        return {
            "by_agent": copy.deepcopy(self._claims),
            "occupied": occupied,
            "duplicates": {slot: agents for slot, agents in occupied.items() if len(agents) > 1},
        }

    def denials(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._denials)
