from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CALLS_PER_CELL = 5
TEMPERATURE = 0
MODEL = "GLM-4-Flash"
PROVIDER = "paratera_glm"
KINDS = ("agent_a_report", "agent_b_report", "coordinator_plan", "agent_a_commit", "agent_b_commit")
DIRECT_KINDS = ("direct_plan",)


@dataclass
class BudgetMeter:
    calls: int = 0
    max_calls: int = CALLS_PER_CELL
    kinds: list[str] = field(default_factory=list)
    expected: tuple[str, ...] = KINDS

    def charge(self, kind: str) -> None:
        self.calls += 1
        self.kinds.append(kind)

    @property
    def valid(self) -> bool:
        return self.calls == self.max_calls and list(self.kinds) == list(self.expected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "max_calls": self.max_calls,
            "kinds": list(self.kinds),
            "expected": list(self.expected),
            "model": MODEL,
            "temperature": TEMPERATURE,
            "valid": self.valid,
        }
