"""Direct final spec: one call, no review, sees the effective version only."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_gm_05b.budget import BudgetMeter

ExecutorFn = Callable[[str], str]


def run_direct_cell(
    *,
    task: dict,
    variant: str,
    task_id: str,
    out_dir: Path,
    executor_fn: ExecutorFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    budget = BudgetMeter(max_calls=1)
    version = "v1" if variant == "control" else "v2"
    brief = task[version]["brief"]
    source = executor_fn(brief) or ""
    budget.charge("direct_final")
    path = out_dir / "artifact_after.py"
    path.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
    (out_dir / "artifact_before.py").write_text("", encoding="utf-8")
    return {
        "events": ["requirement_available", "submitted"],
        "draft": "",
        "final": source,
        "draft_path": str(out_dir / "artifact_before.py"),
        "final_path": str(path),
        "review": {},
        "review_delivered": False,
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "track": "direct_final_spec",
        "visible_brief": brief,
    }
