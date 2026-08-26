"""Versioned shared kernel for GAWorld benchmark experiments.

Frozen experiment directories keep their historical implementation. New
experiments should import contracts from this package instead of copying a
legacy scorer or silently changing a frozen protocol.
"""

from benchmark_core.eval_mode import capture_eval_mode_evidence, eval_mode_gate
from benchmark_core.result import RunContext, compose_cell
from benchmark_core.task_card import TaskCardValidation, validate_task_card

__all__ = [
    "RunContext",
    "TaskCardValidation",
    "capture_eval_mode_evidence",
    "compose_cell",
    "eval_mode_gate",
    "validate_task_card",
]
