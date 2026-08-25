"""Shared v1 draft, then fork Single / Multi / Drop. v2 published after the draft exists."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_t3_01.budget import BudgetMeter
from exp_gm_t3_01.contracts.review_action import action_contract, is_contract_failure, to_channel_payload
from exp_gm_t3_01.inspect import sha256_text, spec_version
from exp_gm_t3_01.loader import leak_tokens_for
from exp_gm_t3_01.roles import builder_draft_prompt, current_private
from gaworld.work.review import ReviewChannel

GenerateFn = Callable[[str], str]
ReviseFn = Callable[[str, str, dict[str, Any] | None], str]
ReviewerFn = Callable[[str, dict[str, Any]], Any]


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def generate_shared_draft(
    *,
    task: dict,
    variant: str,
    repeat_id: int,
    out_dir: Path,
    generate_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    brief_v1 = task["brief"]
    draft_prompt = builder_draft_prompt(brief_v1)
    leaks = leak_tokens_for(task, variant)
    leak_on_first = _contains(draft_prompt, leaks)
    source = generate_fn(draft_prompt) or ""
    sha = sha256_text(source)
    draft_has_v2 = _contains(source, leak_tokens_for(task, "intervention"))
    path = out_dir / "artifact_before.py"
    path.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
    payload = {
        "task_id": task["id"],
        "variant": variant,
        "repeat_id": repeat_id,
        "brief_version": "v1",
        "v2_published": False,
        "sha256": sha,
        "leak_on_first_brief": leak_on_first,
        "generation_prompt": brief_v1,
        "draft_prompt": draft_prompt,
        "draft_prompt_sha256": sha256_text(draft_prompt),
        "draft_has_v2_tokens": draft_has_v2,
    }
    (out_dir / "draft_hash.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "source": source,
        "path": str(path),
        "sha256": sha,
        "brief_v1": brief_v1,
        "leak_on_first_brief": leak_on_first,
        "generation_prompt": brief_v1,
        "draft_prompt": draft_prompt,
        "draft_prompt_sha256": sha256_text(draft_prompt),
        "draft_has_v2_tokens": draft_has_v2,
        "v2_published_after_draft": True,
    }


def run_track_from_draft(
    *,
    task: dict,
    variant: str,
    track: str,
    task_id: str,
    out_dir: Path,
    shared: dict[str, Any],
    revise_fn: ReviseFn,
    reviewer_fn: ReviewerFn,
    drop: bool = False,
    executor_id: int = 5,
    reviewer_id: int = 6,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    budget = BudgetMeter()
    channel = ReviewChannel(str(out_dir / "review.jsonl"))
    draft = shared["source"]
    before = out_dir / "artifact_before.py"
    before.write_text(draft if draft.endswith("\n") else draft + "\n", encoding="utf-8")
    budget.charge("builder_draft")
    events = ["requirement_available", "draft_created", "v2_published" if variant == "intervention" else "v1_still_binding"]
    private = current_private(task, variant)
    channel.put_private(task_id, "reviewer", private)
    channel.write_artifact(task_id=task_id, role="executor", kind="draft", path=str(before), content=draft)
    channel.submit_draft(task_id, executor_id=executor_id, path=str(before), spec_version=spec_version(draft) or "v1")
    channel.request_review(task_id)
    events.append("review_started")
    raw_review = reviewer_fn(draft, private)
    review, contract_error = action_contract(raw_review if isinstance(raw_review, dict) else None)
    budget.charge("review")
    events.append("review_decision")
    (out_dir / "review_raw.json").write_text(json.dumps(raw_review if isinstance(raw_review, dict) else {"raw": raw_review}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    emitted: dict[str, Any] = {"ok": False, "reason": contract_error}
    if contract_error == "ok" and review:
        emitted = channel.emit_review(
            task_id,
            reviewer_id=reviewer_id,
            payload=to_channel_payload(review, task=task, private=private, draft_version=spec_version(draft) or "v1"),
        )
        if emitted.get("ok"):
            events.append("review_emitted")
    (out_dir / "review_action.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_for_builder = None
    delivered = False
    drop_inbox: list[Any] = []
    if track == "single":
        review_for_builder = review if contract_error == "ok" else None
        delivered = contract_error == "ok"
        events.append("review_delivered" if delivered else "review_contract_failed")
    elif drop:
        if contract_error == "ok" and emitted.get("ok"):
            channel.deliver_review(task_id, drop=True)
        events.append("review_dropped")
        drop_inbox = list((channel.read_inbox(task_id, "executor").get("reviews") or []))
    elif contract_error == "ok" and emitted.get("ok"):
        channel.deliver_review(task_id, drop=False)
        delivered = True
        events.append("review_delivered")
        inbox = channel.read_inbox(task_id, "executor")
        items = inbox.get("reviews") or []
        review_for_builder = review
        if items:
            channel.adopt_review(task_id, items[0].get("review_id") or "", current_spec_version=spec_version(draft) or "v1")
    else:
        events.append("review_contract_failed")
    brief_v1 = task["brief"]
    final = revise_fn(brief_v1, draft, review_for_builder) or ""
    budget.charge("builder_final")
    after = out_dir / "artifact_after.py"
    channel.write_artifact(task_id=task_id, role="executor", kind="final", path=str(after), content=final)
    events.append("submitted")
    hidden_in_prompt = []
    first_prompt = str(shared.get("draft_prompt") or shared.get("generation_prompt") or "")
    for text in (first_prompt, brief_v1, json.dumps(review_for_builder) if review_for_builder else ""):
        if "test_parking_" in text or "test_deposit_" in text or "test_queue_" in text:
            hidden_in_prompt.append("oracle_filename")
    reviewer_write = channel.write_artifact(
        task_id=task_id, role="reviewer", kind="final", path=str(out_dir / "stolen.py"), content="x"
    )
    builder_private = channel.read_private(task_id, "executor")
    (out_dir / "shared_draft.json").write_text(
        json.dumps({"sha256": shared["sha256"], "v2_published_after_draft": True}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "events": events,
        "draft": draft,
        "final": final,
        "draft_path": str(before),
        "final_path": str(after),
        "review": review,
        "review_emitted": bool(emitted.get("ok")),
        "review_delivered": delivered,
        "reviewer_ran": True,
        "executor_saw_review": review_for_builder is not None,
        "drop_inbox_empty": (track != "drop") or (len(drop_inbox) == 0),
        "drop_inbox_n": len(drop_inbox),
        "contract_ok": contract_error == "ok",
        "contract_error": contract_error,
        "contract_rejected": is_contract_failure(contract_error),
        "total_model_calls": 3,
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "track": track,
        "shared_draft_sha256": shared["sha256"],
        "v2_published_after_draft": True,
        "leak_on_first_brief": list(shared.get("leak_on_first_brief") or []),
        "draft_prompt_sha256": shared.get("draft_prompt_sha256"),
        "first_prompt": first_prompt,
        "hidden_in_prompt": hidden_in_prompt,
        "reviewer_write": reviewer_write,
        "executor_private": builder_private,
        "builder_private": builder_private,
        "channel": channel,
    }
