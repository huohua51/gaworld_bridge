"""Save → transmit → read. Does not rewrite reviewer payload."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


def canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class IntegrityMailbox:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.reviewer_hash: str | None = None
        self.channel_sent_hash: str | None = None
        self.executor_read_hash: str | None = None
        self.stored: dict[str, Any] | None = None
        self.envelope: dict[str, Any] | None = None
        self.inbox: list[dict[str, Any]] = []
        self.dropped = False
        self.events: list[dict[str, Any]] = []

    def _append(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def emit(self, payload: dict[str, Any], *, artifact_before_hash: str, spec_version: str) -> dict[str, Any]:
        body = copy.deepcopy(payload)
        self.reviewer_hash = canonical_hash(body)
        self.stored = body
        envelope = {
            "review_id": "review-001",
            "spec_version": spec_version,
            "artifact_before_hash": artifact_before_hash,
            "review_payload_hash": self.reviewer_hash,
            "decision": body.get("decision"),
            "required_changes": copy.deepcopy(body.get("required_changes") or []),
        }
        self.envelope = envelope
        self._append({"event": "review_emitted", **envelope, "payload": body})
        return envelope

    def mutate_stored(self, mutator: Callable[[dict[str, Any]], None]) -> None:
        if self.stored is None:
            raise AssertionError("no payload to mutate")
        mutator(self.stored)

    def deliver(self, *, drop: bool) -> dict[str, Any]:
        if self.stored is None:
            raise AssertionError("review not emitted")
        sent = copy.deepcopy(self.stored)
        self.channel_sent_hash = canonical_hash(sent)
        self.dropped = drop
        record = {
            "event": "review_dropped" if drop else "review_delivered",
            "dropped": drop,
            "review_payload_hash": self.channel_sent_hash,
            "payload": sent,
        }
        if not drop:
            self.inbox.append(sent)
        self._append(record)
        return record

    def read(self) -> dict[str, Any] | None:
        if self.dropped or not self.inbox:
            self.executor_read_hash = None
            self._append({"event": "inbox_read", "n": 0, "dropped": self.dropped})
            return None
        payload = copy.deepcopy(self.inbox[0])
        self.executor_read_hash = canonical_hash(payload)
        self._append({"event": "inbox_read", "n": 1, "review_payload_hash": self.executor_read_hash})
        return payload

    def trace(self) -> dict[str, Any]:
        return {
            "reviewer_output_hash": self.reviewer_hash,
            "channel_sent_hash": self.channel_sent_hash,
            "executor_read_hash": self.executor_read_hash,
            "dropped": self.dropped,
            "envelope": self.envelope,
        }

    def hashes_match(self) -> bool:
        if self.dropped:
            return bool(self.reviewer_hash) and self.executor_read_hash is None and not self.inbox
        return bool(self.reviewer_hash) and self.reviewer_hash == self.channel_sent_hash == self.executor_read_hash
