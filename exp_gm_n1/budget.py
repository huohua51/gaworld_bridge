from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CALLS_PER_CELL = 3
TEMPERATURE = 0
MODEL = "GLM-4-Flash"
PROVIDER = "paratera_glm"
KINDS = ("source", "relay", "decision")


@dataclass
class BudgetMeter:
    calls: int = 0
    max_calls: int = CALLS_PER_CELL
    kinds: list[str] = field(default_factory=list)

    def charge(self, kind: str) -> None:
        self.calls += 1
        self.kinds.append(kind)

    @property
    def valid(self) -> bool:
        return self.calls == self.max_calls and list(self.kinds) == list(KINDS)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "max_calls": self.max_calls,
            "kinds": list(self.kinds),
            "model": MODEL,
            "temperature": TEMPERATURE,
            "valid": self.valid,
        }
