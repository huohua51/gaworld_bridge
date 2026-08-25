"""Multi-agent equal-budget track: Executor, Reviewer, Executor rework."""

from __future__ import annotations

from typing import Any

from exp_gm_05.engine import run_cell


def run_multi_cell(**kwargs: Any) -> dict[str, Any]:
    return run_cell(track="multi", drop=False, **kwargs)
