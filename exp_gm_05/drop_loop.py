"""Drop-review equal-budget track. Reviewer still consumes the second call."""

from __future__ import annotations

from typing import Any

from exp_gm_05.engine import run_cell


def run_drop_cell(**kwargs: Any) -> dict[str, Any]:
    return run_cell(track="drop", drop=True, **kwargs)
