"""Executor-only cell. Rule Reviewer supplies a correct patch; model applies it."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_gm_04c.roles import render_source
from exp_gm_04e.executor import typed_patches
from exp_gm_04e.tasks import FACT_SPECS
from gaworld.work.artifact_patches import verify_applied

ExecutorFn = Callable[[str], str]


def run_executor_cell(
    *,
    task: dict,
    protocol: str,
    task_id: str,
    out_dir: Path,
    executor_fn: ExecutorFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    before = render_source(task, "v1")
    (out_dir / "draft_main.py").write_text(before if before.endswith("\n") else before + "\n", encoding="utf-8")
    patches = typed_patches(task, before)
    after = executor_fn(before) or ""
    (out_dir / "final_main.py").write_text(after if after.endswith("\n") else after + "\n", encoding="utf-8")
    verify = verify_applied(before=before, after=after, patches=patches, specs=FACT_SPECS[task["id"]])
    return {
        "events": ["draft_fixed", "patch_delivered", "executor_call_1"],
        "before": before,
        "after": after,
        "patches": patches,
        "verify": verify,
        "patch_applied": bool(verify.get("applied")),
        "executor_calls": 1,
        "first_error": str(verify.get("reason") or "patch_not_read") if not verify.get("applied") else (
            "unregistered_change" if verify.get("reason") == "unregistered_change" else "none"
        ),
        "environment_rewrote": False,
    }
