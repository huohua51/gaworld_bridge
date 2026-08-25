from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MAX_TOKENS = 2048
TEMPERATURE = 0
MODEL = "GLM-4-Flash"
PROVIDER = "paratera_glm"


@dataclass
class BudgetMeter:
    calls: int = 0
    max_calls: int = 1
    kinds: list[str] = field(default_factory=list)

    def charge(self, kind: str) -> None:
        self.calls += 1
        self.kinds.append(kind)

    @property
    def valid(self) -> bool:
        return self.calls == self.max_calls

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "max_calls": self.max_calls,
            "kinds": list(self.kinds),
            "model": MODEL,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "valid": self.valid,
        }
