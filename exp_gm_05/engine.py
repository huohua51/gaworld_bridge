"""Shared three-call cell runner for Single / Multi / Drop."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from exp_gm_05.budget import BudgetMeter
from exp_gm_05.inspect import spec_version
from exp_gm_05.roles import current_private
from exp_gm_05.tasks import leak_tokens_for
from gaworld.work.review import ReviewChannel

ExecutorFn = Callable[[str, str | None, dict[str, Any] | None], str]
ReviewerFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def run_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    executor_fn: ExecutorFn,
    reviewer_fn: ReviewerFn,
    drop: bool = False,
    executor_id: int = 5,
    reviewer_id: int = 6,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel = ReviewChannel(str(out_dir / "review.jsonl"))
    budget = BudgetMeter()
    events: list[str] = ["requirement_available"]
    trace = out_dir / "canonical_trace.jsonl"
    private = current_private(task, variant)
    leaks = leak_tokens_for(task, variant)
    channel.put_private(task_id, "reviewer", private)
    brief_v1 = task["v1"]["brief"]
    leak_on_first = _contains(brief_v1, leaks)
    visible: list[str] = []

    def _trace(event: str, **extra: Any) -> None:
        row = {"event": event, **extra}
        with trace.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    started = time.time()
    _trace("requirement_available", variant=variant, track=track)
    draft = executor_fn(brief_v1, None, None) or ""
    budget.charge("executor_draft", elapsed_s=time.time() - started, prompt_chars=len(brief_v1))
    visible.append(brief_v1)
    draft_path = out_dir / "artifact_before.py"
    written = channel.write_artifact(
        task_id=task_id, role="executor", kind="draft", path=str(draft_path), content=draft,
    )
    events.append("draft_created")
    _trace("draft_created", ok=written.get("ok"), path=str(draft_path))
    channel.submit_draft(task_id, executor_id=executor_id, path=str(draft_path), spec_version=spec_version(draft) or "v1")

    events.append("review_started")
    channel.request_review(task_id)
    started = time.time()
    review = reviewer_fn(draft, private) or {}
    budget.charge("review", elapsed_s=time.time() - started, prompt_chars=len(draft) + len(json.dumps(private)))
    events.append("review_decision")
    _trace("review_started")
    emitted = channel.emit_review(task_id, reviewer_id=reviewer_id, payload=review)
    _trace("review_decision", ok=emitted.get("ok"), decision=(review or {}).get("decision"))
    (out_dir / "review_action.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    review_for_exec = None
    delivered = False
    if track == "single":
        review_for_exec = review
        delivered = True
        events.append("review_delivered")
        _trace("review_delivered", mode="self_check")
    else:
        delivered_out = channel.deliver_review(task_id, drop=drop)
        if drop:
            events.append("review_dropped")
            _trace("review_dropped", ok=delivered_out.get("ok"))
        else:
            delivered = True
            events.append("review_delivered")
            inbox = channel.read_inbox(task_id, "executor")
            reviews = inbox.get("reviews") or []
            review_for_exec = reviews[0] if reviews else None
            if review_for_exec:
                channel.adopt_review(
                    task_id, review_for_exec.get("review_id") or "", current_spec_version=spec_version(draft) or "v1"
                )
            _trace("review_delivered", ok=delivered_out.get("ok"))

    started = time.time()
    final = executor_fn(brief_v1, draft, review_for_exec) or ""
    third_prompt = brief_v1 + (draft or "") + (json.dumps(review_for_exec) if review_for_exec else "")
    budget.charge("executor_final", elapsed_s=time.time() - started, prompt_chars=len(third_prompt))
    visible.append(third_prompt)
    final_path = out_dir / "artifact_after.py"
    channel.write_artifact(task_id=task_id, role="executor", kind="final", path=str(final_path), content=final)
    events.append("change_adopted")
    events.append("submitted")
    _trace("submitted", budget_calls=budget.calls)

    oracle_leak = []
    for token in leaks:
        if any(token in text for text in visible[:1]) and variant == "intervention":
            oracle_leak.append(token)
    hidden_in_prompt = []
    for text in visible:
        if "test_aid_" in text or "test_roster_" in text or "test_routing_" in text:
            hidden_in_prompt.append("oracle_filename")

    reviewer_write = channel.write_artifact(
        task_id=task_id, role="reviewer", kind="final", path=str(out_dir / "reviewer_forbidden.py"), content="stolen",
    )
    executor_private = channel.read_private(task_id, "executor")

    (out_dir / "run_manifest.json").write_text(
        json.dumps(
            {"task_id": task["id"], "variant": variant, "track": track, "budget": budget.to_dict()},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "events": events,
        "draft": draft,
        "final": final,
        "draft_path": str(draft_path),
        "final_path": str(final_path),
        "review": review,
        "review_delivered": delivered,
        "review_emitted": bool(emitted.get("ok")),
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "leak_on_first_brief": leak_on_first,
        "hidden_in_prompt": hidden_in_prompt,
        "reviewer_write": reviewer_write,
        "executor_private": executor_private,
        "private_ok": True,
        "channel_denials": list(channel._denials),
        "inbox_empty": drop,
    }
