"""Orchestrate Focused / Full-review / Drop-review cells without leaking v2."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable

from exp_gm_04b.versioning import parse_artifact_spec_version
from exp_gm_04c.roles import expected_review_decision, inspect_draft
from exp_gm_04c.tasks import leak_tokens_for, private_payload

ExecutorFn = Callable[[str, dict[str, Any] | None], str]
ReviewerFn = Callable[[str, dict[str, Any]], dict[str, Any]]


def _same_change(got: dict, required: dict) -> bool:
    if set(got) != set(required):
        return False
    for key, want in required.items():
        have = got.get(key)
        if have == want:
            continue
        try:
            if float(have) == float(want):
                continue
        except (TypeError, ValueError):
            return False
        return False
    return True


def _contains_leak(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def _copy(src: str | None, dest: Path) -> str | None:
    if not src or not os.path.isfile(src):
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    return str(dest)


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
    from gaworld.work.ingest import absorb_completed_for
    from gaworld.work.queue import WorkQueue
    from gaworld.work.review import ReviewChannel
    from gaworld.work.schemas import WorkBrief, WorkResult

    out_dir.mkdir(parents=True, exist_ok=True)
    channel = ReviewChannel(str(out_dir / "review.jsonl"))
    queue = WorkQueue(str(out_dir / "queue.jsonl"))
    events: list[str] = []
    expected_version = "v1" if variant == "control" else "v2"
    private = private_payload(task, expected_version)
    leak_tokens = leak_tokens_for(task, variant)
    executor_visible: list[str] = []
    executor_calls = 0
    reviewer_calls = 0
    draft_path = None
    final_path = None
    review_action = None
    adopt = None
    inbox = None
    first_brief = brief_v1 if track != "focused" or variant == "control" else brief_v2

    def _exec(brief_text: str, review: dict[str, Any] | None) -> str:
        nonlocal executor_calls
        executor_calls += 1
        executor_visible.append(brief_text + (("\n" + str(review)) if review else ""))
        return executor_fn(brief_text, review)

    def _write(kind: str, source: str) -> dict[str, Any]:
        path = str(out_dir / ("draft_main.py" if kind == "draft" else "final_main.py"))
        return channel.write_artifact(task_id=task_id, role="executor", kind=kind, path=path, content=source)

    if track != "focused":
        channel.put_private(task_id, "reviewer", private)

    leak_on_first = _contains_leak(first_brief, leak_tokens) if track != "focused" else []

    if track == "focused":
        events.append("focused_brief")
        source = _exec(first_brief, None)
        written = _write("final", source)
        final_path = written.get("path")
        events.append("adapter_run")
        if final_path:
            events.append("artifact_written")
    else:
        events.append("queue_submit")
        brief = WorkBrief(
            task_id=task_id,
            agent_id=executor_id,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="按 brief 写脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=brief_v1,
            estimated_minutes=15,
            submitted_at=time.time(),
            spec_version="v1",
        )
        queue.submit(brief)
        claimed = queue.claim_next()
        if claimed:
            events.append("queue_claim")
        source = _exec(brief_v1, None)
        draft_write = _write("draft", source)
        draft_path = draft_write.get("path")
        events.append("executor_draft")
        submitted = channel.submit_draft(
            task_id, executor_id=executor_id, path=draft_path or "", spec_version="v1"
        )
        if submitted.get("ok"):
            events.append("draft_submitted")
        requested = channel.request_review(task_id)
        if requested.get("ok"):
            events.append("review_requested")
        private_read = channel.read_private(task_id, "reviewer")
        if reviewer_fn is None:
            raise ValueError("reviewer_fn required for review tracks")
        reviewer_calls += 1
        raw_action = reviewer_fn(source, private_read.get("payload") or {})
        emitted = channel.emit_review(task_id, reviewer_id=reviewer_id, payload=raw_action)
        if emitted.get("ok"):
            events.append("review_emitted")
            review_action = emitted.get("action")
        drop = track == "drop_review"
        delivered = channel.deliver_review(task_id, drop=drop)
        if delivered.get("ok") and drop:
            events.append("review_dropped")
        elif delivered.get("ok"):
            events.append("review_delivered")
        inbox = channel.read_inbox(task_id, "executor")
        if inbox.get("ok"):
            events.append("review_read")
        reviews = inbox.get("reviews") or []
        if reviews:
            review_action = reviews[0]
            draft_version = parse_artifact_spec_version(draft_path) or "v1"
            adopt = channel.adopt_review(
                task_id, review_action["review_id"], current_spec_version=draft_version
            )
            if adopt.get("ok"):
                events.append("review_adopted")
                if review_action.get("decision") == "revise":
                    rework = _exec(brief_v1, review_action)
                    final_write = _write("final", rework)
                    final_path = final_write.get("path")
                    events.append("executor_rework")
                else:
                    copied = _copy(draft_path, out_dir / "final_main.py")
                    if copied:
                        channel.write_artifact(
                            task_id=task_id, role="executor", kind="final",
                            path=copied, content=Path(copied).read_text(encoding="utf-8"),
                        )
                    final_path = copied
                    events.append("reviewer_approve")
        elif drop:
            retry = _exec(brief_v1, None)
            final_write = _write("final", retry)
            final_path = final_write.get("path")
            events.append("executor_retry_without_review")
        else:
            copied = _copy(draft_path, out_dir / "final_main.py")
            final_path = copied
        if final_path:
            events.append("final_result")
            queue.record_result(WorkResult(
                task_id=task_id,
                agent_id=executor_id,
                status="ok",
                artifact_paths=[final_path],
                summary="review loop final",
                finished_at=time.time(),
            ))
            events.append("queue_result")
            agent = {"id": executor_id, "name": "王思远", "state": {}, "memory": []}
            absorbed = absorb_completed_for(
                agent, queue=queue, market=None, sim_day=1, sim_time="10:00", limit=5
            )
            if absorbed:
                events.append("absorb")

    unauthorized = [
        item for item in channel.denials()
        if item.get("reason") in {"unauthorized_private_read", "unauthorized_artifact_write"}
    ]
    expected_decision = expected_review_decision(variant) if track != "focused" else None
    advice_correct = None
    if review_action and expected_decision:
        advice_correct = review_action.get("decision") == expected_decision
        if expected_decision == "revise":
            required = dict(task["change_v2"])
            got = dict(review_action.get("required_change") or {})
            advice_correct = bool(
                advice_correct
                and review_action.get("required_spec_version") == "v2"
                and _same_change(got, required)
            )
    draft_inspect = inspect_draft(Path(draft_path).read_text(encoding="utf-8"), task) if draft_path and os.path.isfile(draft_path) else {}
    final_inspect = inspect_draft(Path(final_path).read_text(encoding="utf-8"), task) if final_path and os.path.isfile(final_path) else {}
    leaked_after = []
    if track == "drop_review":
        leaked_after = _contains_leak("\n".join(executor_visible[1:]), leak_tokens) if len(executor_visible) > 1 else []
    return {
        "events": events,
        "channel": channel,
        "queue": queue,
        "draft_path": draft_path,
        "final_path": final_path,
        "review_action": review_action,
        "adopt": adopt,
        "inbox": inbox,
        "executor_calls": executor_calls,
        "reviewer_calls": reviewer_calls,
        "expected_version": expected_version,
        "expected_decision": expected_decision,
        "review_advice_correct": advice_correct,
        "leak_on_first_brief": leak_on_first,
        "leak_on_drop_retry": leaked_after,
        "executor_read_private": any(
            d.get("reason") == "unauthorized_private_read" and d.get("role") == "executor"
            for d in channel.denials()
        ),
        "reviewer_wrote_artifact": any(
            d.get("reason") == "unauthorized_artifact_write" and d.get("role") == "reviewer"
            for d in channel.denials()
        ),
        "unauthorized": unauthorized,
        "draft_inspect": draft_inspect,
        "final_inspect": final_inspect,
        "private_ok": track == "focused" or bool(channel.read_private(task_id, "reviewer").get("ok")),
        "dropped": track == "drop_review",
        "inbox_empty": not ((inbox or {}).get("reviews") or []),
    }
