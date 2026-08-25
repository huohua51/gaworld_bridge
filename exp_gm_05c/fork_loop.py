"""Shared v1 draft, then fork into Single / Multi / Drop. v2 is published after the draft exists."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_05c.budget import BudgetMeter
from exp_gm_05c.contract import ContractResult, channel_payload, validate_action
from exp_gm_05c.inspect import sha256_text, spec_version
from exp_gm_05c.roles import current_private
from exp_gm_05c.tasks import leak_tokens_for
from gaworld.work.review import ReviewChannel

GenerateFn = Callable[[str], str]
ReviseFn = Callable[[str, str, dict[str, Any] | None], str]
ReviewerFn = Callable[[str, dict[str, Any]], Any]


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def _as_contract(review_out: Any) -> ContractResult:
    if isinstance(review_out, ContractResult):
        return review_out
    if isinstance(review_out, dict) and review_out.get("decision"):
        return validate_action(review_out)
    return ContractResult(False, None, "prose_only", problems=["empty_or_invalid_review"])


def generate_shared_draft(
    *,
    task: dict,
    variant: str,
    repeat_id: int,
    out_dir: Path,
    generate_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    brief_v1 = task["v1"]["brief"]
    leaks = leak_tokens_for(task, variant)
    leak_on_first = _contains(brief_v1, leaks)
    source = generate_fn(brief_v1) or ""
    sha = sha256_text(source)
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
    }
    (out_dir / "draft_hash.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "source": source,
        "path": str(path),
        "sha256": sha,
        "brief_v1": brief_v1,
        "leak_on_first_brief": leak_on_first,
        "generation_prompt": brief_v1,
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
    contract = _as_contract(reviewer_fn(draft, private))
    budget.charge("review")
    review = dict(contract.action or {})
    events.append("review_decision")
    (out_dir / "review_raw.txt").write_text(contract.raw or json.dumps(review, ensure_ascii=False), encoding="utf-8")
    if contract.retry_raw:
        (out_dir / "review_retry_raw.txt").write_text(contract.retry_raw, encoding="utf-8")
    emitted: dict[str, Any] = {"ok": False, "reason": contract.error or "contract_invalid"}
    if contract.ok and review:
        emitted = channel.emit_review(
            task_id,
            reviewer_id=reviewer_id,
            payload=channel_payload(
                review,
                draft_version=spec_version(draft) or "v1",
                private=private,
                criterion_id=str(task["criterion_id"]),
            ),
        )
    (out_dir / "review_action.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "review_contract.json").write_text(
        json.dumps(contract.to_meta(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    review_for_builder = None
    delivered = False
    if track == "single":
        review_for_builder = review if contract.ok else None
        delivered = bool(contract.ok)
        events.append("review_delivered" if delivered else "review_contract_failed")
    elif drop:
        if contract.ok:
            channel.deliver_review(task_id, drop=True)
        events.append("review_dropped")
    elif contract.ok:
        channel.deliver_review(task_id, drop=False)
        delivered = True
        events.append("review_delivered")
        inbox = channel.read_inbox(task_id, "executor")
        items = inbox.get("reviews") or []
        review_for_builder = review
        if items:
            channel.adopt_review(
                task_id,
                items[0].get("review_id") or "",
                current_spec_version=spec_version(draft) or "v1",
            )
    else:
        events.append("review_contract_failed")
    brief_v1 = task["v1"]["brief"]
    final = revise_fn(brief_v1, draft, review_for_builder) or ""
    budget.charge("builder_final")
    after = out_dir / "artifact_after.py"
    channel.write_artifact(task_id=task_id, role="executor", kind="final", path=str(after), content=final)
    events.append("submitted")
    hidden_in_prompt = []
    for text in (shared.get("generation_prompt") or "", brief_v1, json.dumps(review_for_builder) if review_for_builder else ""):
        if "test_aid_" in text or "test_hours_" in text or "test_route_" in text:
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
        "contract_ok": contract.ok,
        "contract": contract.to_meta(),
        "contract_retry_used": contract.contract_retry_used,
        "contract_retry_success": contract.contract_retry_success,
        "total_model_calls": 2 + int(contract.total_review_calls or 1),
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "track": track,
        "shared_draft_sha256": shared["sha256"],
        "v2_published_after_draft": True,
        "leak_on_first_brief": list(shared.get("leak_on_first_brief") or []),
        "hidden_in_prompt": hidden_in_prompt,
        "reviewer_write": reviewer_write,
        "executor_private": builder_private,
        "builder_private": builder_private,
    }
