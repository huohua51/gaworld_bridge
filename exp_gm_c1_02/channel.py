"""Save → transmit → read. Does not rewrite payloads. Coordinator cannot execute."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROLES = ("agent_a", "agent_b", "coordinator", "environment")


def canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CoordinationChannel:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._private: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, dict[str, Any]] = {}
        self._report_inbox: dict[str, dict[str, Any]] = {}
        self._revisions: dict[str, dict[str, Any]] = {}
        self._revision_inbox: dict[str, dict[str, Any]] = {}
        self._plan: dict[str, Any] | None = None
        self._plan_inbox: dict[str, Any] | None = None
        self._claims: list[dict[str, Any]] = []
        self._denials: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.dropped_reports: set[str] = set()
        self.dropped_revisions: set[str] = set()
        self.plan_dropped = False

    def _append(self, event: dict[str, Any]) -> None:
        self.events.append(event)
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
            return self._deny("private_owner_must_be_agent", role=owner)
        body = copy.deepcopy(payload)
        self._private[owner] = body
        self._append({"event": "private_put", "role": owner, "payload": body})
        return {"ok": True, "role": owner}

    def read_private(self, reader: str, owner: str) -> dict[str, Any]:
        if reader != owner:
            return self._deny("unauthorized_private_read", role=reader, owner=owner)
        payload = self._private.get(owner)
        if payload is None:
            return self._deny("private_context_missing", role=reader, owner=owner)
        self._append({"event": "private_read", "role": reader, "owner": owner})
        return {"ok": True, "payload": copy.deepcopy(payload)}

    def emit_report(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if agent_id not in {"agent_a", "agent_b"}:
            return self._deny("invalid_reporter", role=agent_id)
        body = copy.deepcopy(payload)
        digest = canonical_hash(body)
        self._reports[agent_id] = body
        self._append({"event": "report_emitted", "agent_id": agent_id, "hash": digest, "payload": body})
        return {"ok": True, "hash": digest, "payload": body}

    def deliver_report(self, agent_id: str, *, drop: bool = False) -> dict[str, Any]:
        body = self._reports.get(agent_id)
        if body is None:
            return self._deny("report_not_emitted", agent_id=agent_id)
        digest = canonical_hash(body)
        if drop:
            self.dropped_reports.add(agent_id)
            self._append({"event": "report_dropped", "agent_id": agent_id, "hash": digest})
            return {"ok": True, "dropped": True, "hash": digest}
        self._report_inbox[agent_id] = copy.deepcopy(body)
        self._append({"event": "report_delivered", "agent_id": agent_id, "hash": digest})
        return {"ok": True, "dropped": False, "hash": digest}

    def emit_revision(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if agent_id != "agent_b":
            return self._deny("invalid_reviser", role=agent_id)
        body = copy.deepcopy(payload)
        digest = canonical_hash(body)
        self._revisions[agent_id] = body
        self._append({"event": "revision_emitted", "agent_id": agent_id, "hash": digest, "payload": body})
        return {"ok": True, "hash": digest}

    def deliver_revision(self, agent_id: str, *, drop: bool) -> dict[str, Any]:
        body = self._revisions.get(agent_id)
        if body is None:
            return self._deny("revision_not_emitted", agent_id=agent_id)
        digest = canonical_hash(body)
        if drop:
            self.dropped_revisions.add(agent_id)
            self._append({"event": "revision_dropped", "agent_id": agent_id, "hash": digest})
            return {"ok": True, "dropped": True, "hash": digest}
        self._revision_inbox[agent_id] = copy.deepcopy(body)
        self._append({"event": "revision_delivered", "agent_id": agent_id, "hash": digest})
        return {"ok": True, "dropped": False, "hash": digest}

    def read_reports(self, reader: str) -> dict[str, Any]:
        if reader != "coordinator":
            return self._deny("unauthorized_inbox_read", role=reader)
        inbox = copy.deepcopy(self._report_inbox)
        self._append({"event": "reports_read", "role": reader, "agents": sorted(inbox)})
        return {"ok": True, "reports": inbox}

    def read_revisions(self, reader: str) -> dict[str, Any]:
        if reader != "coordinator":
            return self._deny("unauthorized_inbox_read", role=reader)
        inbox = copy.deepcopy(self._revision_inbox)
        self._append({"event": "revisions_read", "role": reader, "agents": sorted(inbox)})
        return {"ok": True, "revisions": inbox}

    def emit_plan(self, payload: dict[str, Any], *, role: str = "coordinator") -> dict[str, Any]:
        if role != "coordinator":
            return self._deny("unauthorized_plan_emit", role=role)
        body = copy.deepcopy(payload)
        digest = canonical_hash(body)
        self._plan = body
        self._append({"event": "plan_emitted", "hash": digest, "payload": body})
        return {"ok": True, "hash": digest}

    def deliver_plan(self, *, drop: bool = False) -> dict[str, Any]:
        if self._plan is None:
            return self._deny("plan_not_emitted")
        digest = canonical_hash(self._plan)
        if drop:
            self.plan_dropped = True
            self._plan_inbox = None
            self._append({"event": "plan_dropped", "hash": digest})
            return {"ok": True, "dropped": True, "hash": digest}
        self._plan_inbox = copy.deepcopy(self._plan)
        self._append({"event": "plan_delivered", "hash": digest})
        return {"ok": True, "dropped": False, "hash": digest}

    def read_plan(self, reader: str) -> dict[str, Any]:
        if reader not in {"agent_a", "agent_b"}:
            return self._deny("unauthorized_plan_read", role=reader)
        if self._plan_inbox is None:
            return self._deny("plan_not_delivered", role=reader)
        self._append({"event": "plan_read", "role": reader})
        return {"ok": True, "plan": copy.deepcopy(self._plan_inbox)}

    def submit_claim(self, *, role: str, agent_id: str, slot: str, plan_version: str) -> dict[str, Any]:
        if role not in {"agent_a", "agent_b"}:
            return self._deny("unauthorized_world_write", role=role)
        if role != agent_id:
            return self._deny("claim_agent_mismatch", role=role, agent_id=agent_id)
        claim = {"agent_id": agent_id, "slot": slot, "plan_version": plan_version}
        self._claims.append(claim)
        self._append({"event": "claim_submitted", **claim})
        return {"ok": True, "claim": claim}

    def write_world(self, *, role: str, path: Path, content: str) -> dict[str, Any]:
        if role not in {"agent_a", "agent_b"}:
            return self._deny("unauthorized_world_write", role=role, path=str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
        self._append({"event": "world_write", "role": role, "path": str(path)})
        return {"ok": True, "path": str(path)}

    def world_state(self) -> dict[str, Any]:
        occupied: dict[str, list[str]] = {}
        by_agent: dict[str, str] = {}
        for claim in self._claims:
            occupied.setdefault(claim["slot"], []).append(claim["agent_id"])
            by_agent[claim["agent_id"]] = claim["slot"]
        duplicates = {slot: agents for slot, agents in occupied.items() if len(agents) > 1}
        return {
            "claims": list(self._claims),
            "by_agent": by_agent,
            "occupied": {slot: list(agents) for slot, agents in occupied.items()},
            "duplicates": duplicates,
        }

    def denials(self) -> list[dict[str, Any]]:
        return list(self._denials)

    def latest_delivered_constraints(self) -> dict[str, dict[str, Any]]:
        latest = copy.deepcopy(self._report_inbox)
        latest.update(copy.deepcopy(self._revision_inbox))
        return latest
