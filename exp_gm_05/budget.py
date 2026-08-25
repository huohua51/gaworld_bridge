"""Equal call budget for Single / Multi / Drop. Token use may differ; record it."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CALLS_PER_CELL = 3
MAX_TOKENS = 2048
TEMPERATURE = 0
MODEL = "GLM-4-Flash"
PROVIDER = "paratera_glm"


@dataclass
class BudgetMeter:
    calls: int = 0
    max_calls: int = CALLS_PER_CELL
    kinds: list[str] = field(default_factory=list)
    elapsed_s: list[float] = field(default_factory=list)
    prompt_chars: list[int] = field(default_factory=list)

    def charge(self, kind: str, *, elapsed_s: float = 0.0, prompt_chars: int = 0) -> None:
        self.calls += 1
        self.kinds.append(kind)
        self.elapsed_s.append(elapsed_s)
        self.prompt_chars.append(prompt_chars)

    @property
    def valid(self) -> bool:
        return self.calls == self.max_calls

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "max_calls": self.max_calls,
            "kinds": list(self.kinds),
            "elapsed_s": list(self.elapsed_s),
            "prompt_chars": list(self.prompt_chars),
            "total_elapsed_s": round(sum(self.elapsed_s), 3),
            "model": MODEL,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "valid": self.valid,
        }
