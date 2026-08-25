"""Reuse 04c loop. Protocol extras are stashed because ReviewAction strips unknown fields."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from exp_gm_04c.loop import run_cell_loop as run_04c_loop
from exp_gm_04d.protocol import parse_applied_patch_ids, patch_ids_of
from exp_gm_04d.roles import inspect_draft

ExecutorFn = Callable[[str, dict[str, Any] | None], str]
ReviewerFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def run_cell_loop(
    *,
    task: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    executor_fn: ExecutorFn,
    reviewer_fn: ReviewerFn | None,
    brief_v1: str,
    brief_v2: str,
    executor_id: int = 5,
    reviewer_id: int = 6,
) -> dict[str, Any]:
    stashed: dict[str, Any] = {}

    def _reviewer(draft: str, private: dict[str, Any]) -> dict[str, Any]:
        if reviewer_fn is None:
            raise ValueError("reviewer_fn required")
        raw = reviewer_fn(draft, private)
        stashed["freeze_ok"] = raw.get("_freeze_ok")
        stashed["mismatches"] = list(raw.get("_mismatches") or [])
        stashed["protocol"] = raw.get("_protocol") or raw
        return {key: value for key, value in raw.items() if not str(key).startswith("_")}

    def _executor(brief: str, review: dict[str, Any] | None) -> str:
        if review is not None:
            review = {
                **review,
                "_mismatches": stashed.get("mismatches") or [],
                "_protocol": stashed.get("protocol") or {},
                "_freeze_ok": stashed.get("freeze_ok"),
            }
        return executor_fn(brief, review)

    loop = run_04c_loop(
        task=task,
        variant=variant,
        track=track,
        task_id=task_id,
        out_dir=out_dir,
        executor_fn=_executor,
        reviewer_fn=_reviewer if reviewer_fn is not None else None,
        brief_v1=brief_v1,
        brief_v2=brief_v2,
        executor_id=executor_id,
        reviewer_id=reviewer_id,
    )
    final_path = loop.get("final_path")
    source = ""
    if final_path:
        try:
            source = Path(final_path).read_text(encoding="utf-8")
        except OSError:
            source = ""
    inspect = inspect_draft(source, task) if source else {}
    review = dict(loop.get("review_action") or {})
    mismatches = list(stashed.get("mismatches") or [])
    claimed = parse_applied_patch_ids(source)
    required_ids = patch_ids_of(mismatches)
    required = dict(review.get("required_change") or {})
    observed = dict(inspect.get("observed") or {})
    values_applied = bool(required) and all(observed.get(k) == v for k, v in required.items())
    ids_claimed = (not required_ids) or all(item in claimed for item in required_ids)
    loop["final_inspect"] = {**(loop.get("final_inspect") or {}), **inspect, "applied_patch_ids": claimed}
    loop["freeze_ok"] = stashed.get("freeze_ok")
    loop["patch_adoption"] = bool(review.get("decision") == "revise" and values_applied and ids_claimed)
    loop["false_positive_revision"] = bool(variant == "control" and review.get("decision") == "revise")
    loop["mismatches"] = mismatches
    return loop
