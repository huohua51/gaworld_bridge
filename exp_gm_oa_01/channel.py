"""Local change-gate channel. The environment never rewrites the plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NONE = "NONE"
ENV_REWRITE = "environment_rewrote_plan"


class ChangeGateChannel:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.task_id = ""
        self.initial_plan: dict[str, Any] = {}
        self.plan: dict[str, Any] = {}
        self.injected: dict[str, Any] | None = None
        self.submitted: dict[str, Any] | None = None
        self.denials: list[dict[str, Any]] = []
        self.environment_mutated = False

    def _log(self, kind: str, payload: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"kind": kind, **payload}, ensure_ascii=False) + "\n")

    def register_plan(self, task_id: str, plan: dict[str, Any]) -> None:
        self.task_id = task_id
        self.initial_plan = dict(plan)
        self.plan = dict(plan)
        self._log("register_plan", {"task_id": task_id, "plan": dict(plan)})

    def inject_event(self, task_id: str, notice: dict[str, Any]) -> dict[str, Any]:
        self.injected = dict(notice)
        self._log("inject", {"task_id": task_id, "notice": dict(notice)})
        return {"ok": True, "notice": dict(notice)}

    def seed_notice(self) -> dict[str, Any]:
        if not self.injected:
            return {"ok": False, "reason": "event_not_injected"}
        return {"ok": True, "notice": dict(self.injected)}

    def submit_action(
        self,
        task_id: str,
        *,
        agent_id: int,
        payload: dict[str, Any],
        role: str = "agent",
    ) -> dict[str, Any]:
        if role != "agent":
            return self.rewrite_plan(task_id, role=role, payload=payload)
        self.submitted = dict(payload)
        if payload.get("action") == "revise":
            target = payload.get("target")
            if target and target != NONE:
                self.plan = dict(self.plan)
                self.plan[str(target)] = payload.get("value")
                self.plan["last_revision"] = {
                    "target": target,
                    "value": payload.get("value"),
                    "by": "agent",
                }
        self._log(
            "submit",
            {"task_id": task_id, "agent_id": agent_id, "role": role, "payload": dict(payload)},
        )
        return {"ok": True, "action": dict(payload), "plan": dict(self.plan)}

    def rewrite_plan(
        self,
        task_id: str,
        *,
        role: str,
        payload: dict[str, Any] | None = None,
        target: str | None = None,
        value: Any = None,
    ) -> dict[str, Any]:
        self.environment_mutated = True
        denial = {
            "ok": False,
            "reason": ENV_REWRITE,
            "source": role,
            "task_id": task_id,
            "payload": payload,
            "target": target,
            "value": value,
        }
        self.denials.append(denial)
        self._log("deny_rewrite", denial)
        return denial

    def plan_drift_without_agent_revise(self) -> bool:
        if (self.submitted or {}).get("action") == "revise":
            return False
        return self.plan != self.initial_plan
