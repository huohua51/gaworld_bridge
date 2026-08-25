"""Fixed v1 draft. Single/Multi/Drop each use two model calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_05b.artifacts import render_source
from exp_gm_05b.budget import BudgetMeter
from exp_gm_05b.tasks import private_payload
from gaworld.work.review import ReviewChannel

ExecutorFn = Callable[[str, str, dict[str, Any] | None], str]
ReviewerFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def run_review_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    executor_fn: ExecutorFn,
    reviewer_fn: ReviewerFn,
    drop: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    budget = BudgetMeter(max_calls=2)
    channel = ReviewChannel(str(out_dir / "review.jsonl"))
    draft = render_source(task, "v1")
    before = out_dir / "artifact_before.py"
    before.write_text(draft if draft.endswith("\n") else draft + "\n", encoding="utf-8")
    private = private_payload(task, "v1" if variant == "control" else "v2")
    channel.put_private(task_id, "reviewer", private)
    events = ["requirement_available", "draft_created"]
    channel.write_artifact(task_id=task_id, role="executor", kind="draft", path=str(before), content=draft)
    channel.submit_draft(task_id, executor_id=5, path=str(before), spec_version="v1")
    channel.request_review(task_id)
    events.append("review_started")
    review = reviewer_fn(draft, private) or {}
    budget.charge("review")
    events.append("review_decision")
    emitted = channel.emit_review(task_id, reviewer_id=6, payload=review)
    (out_dir / "review_action.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_for_exec = None
    delivered = False
    if track == "single":
        review_for_exec = review
        delivered = True
        events.append("review_delivered")
    else:
        channel.deliver_review(task_id, drop=drop)
        if drop:
            events.append("review_dropped")
        else:
            delivered = True
            events.append("review_delivered")
            inbox = channel.read_inbox(task_id, "executor")
            items = inbox.get("reviews") or []
            review_for_exec = items[0] if items else None
    brief = task["v1"]["brief"]
    final = executor_fn(brief, draft, review_for_exec) or ""
    budget.charge("executor_final")
    after = out_dir / "artifact_after.py"
    channel.write_artifact(task_id=task_id, role="executor", kind="final", path=str(after), content=final)
    events.append("submitted")
    reviewer_write = channel.write_artifact(
        task_id=task_id, role="reviewer", kind="final", path=str(out_dir / "stolen.py"), content="x"
    )
    executor_private = channel.read_private(task_id, "executor")
    return {
        "events": events,
        "draft": draft,
        "final": final,
        "draft_path": str(before),
        "final_path": str(after),
        "review": review,
        "review_emitted": bool(emitted.get("ok")),
        "review_delivered": delivered,
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "track": track,
        "reviewer_write": reviewer_write,
        "executor_private": executor_private,
    }
