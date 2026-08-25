"""Single-agent equal-budget track: draft, self-check, revise/confirm."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from exp_gm_05.engine import run_cell


def run_single_cell(**kwargs: Any) -> dict[str, Any]:
    return run_cell(track="single", drop=False, **kwargs)
