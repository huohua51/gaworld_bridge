"""Shared v1 draft, then Direct / Single / Multi / Drop with CHANGE→APPLY payload trace."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from cal_gm_apply_01.inspect import parse_source
from exp_gm_t3_01.budget import BudgetMeter
from exp_gm_t3_01.inspect import sha256_text, spec_version
from exp_gm_t3_02.contract import action_contract
from exp_gm_t3_02.integrity import IntegrityMailbox
from holdout_t3.loader import leak_tokens_for
from holdout_t3.prompts import draft_prompt, executor_prompt
from gaworld.work.review import ReviewChannel

GenerateFn = Callable[[str], str]
ReviseFn = Callable[[str, dict[str, Any] | None], str]
ReviewerFn = Callable[[str], Any]

ORACLE_FILE_MARKERS = ("test_t303_", "test_ship_", "test_redeem_", "test_alert_", "test_parking_", "test_deposit_", "test_queue_")


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
    prompt = draft_prompt(task)
    leaks = leak_tokens_for(task, variant)
    leak_on_first = _contains(prompt, leaks)
    raw = generate_fn(prompt) or ""
    source = parse_source(raw)
    sha = sha256_text(source)
    path = out_dir / "artifact_before.py"
    path.write_text(source, encoding="utf-8")
    payload = {
        "task_id": task["id"],
        "variant": variant,
        "repeat_id": repeat_id,
        "sha256": sha,
        "leak_on_first_brief": leak_on_first,
        "draft_prompt": prompt,
        "draft_prompt_sha256": sha256_text(prompt),
        "draft_has_v2_tokens": _contains(source, leak_tokens_for(task, "intervention")),
    }
    (out_dir / "draft_hash.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "source": source,
        "path": str(path),
        "sha256": sha,
        "leak_on_first_brief": leak_on_first,
        "draft_prompt": prompt,
        "draft_prompt_sha256": sha256_text(prompt),
        "draft_has_v2_tokens": payload["draft_has_v2_tokens"],
        "raw_draft": raw,
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
    mutate_fn: Callable[[IntegrityMailbox], None] | None = None,
    skip_inbox: bool = False,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    budget = BudgetMeter()
    channel = ReviewChannel(str(out_dir / "review_acl.jsonl"))
    mailbox = IntegrityMailbox(out_dir / "review_trace.jsonl")
    draft = shared["source"]
    before = out_dir / "artifact_before.py"
    before.write_text(draft if draft.endswith("\n") else draft + "\n", encoding="utf-8")
    budget.charge("builder_draft")
    events = ["requirement_available", "draft_created", "v2_published" if variant == "intervention" else "v1_still_binding"]
    private = {
        "path": task["symbol"],
        "required": task["change_v2"][task["target"]] if variant == "intervention" else task["change_v1"][task["target"]],
        "spec_version": "v2" if variant == "intervention" else "v1",
    }
    channel.put_private(task_id, "reviewer", private)
    channel.write_artifact(task_id=task_id, role="executor", kind="draft", path=str(before), content=draft)
    channel.submit_draft(task_id, executor_id=executor_id, path=str(before), spec_version=spec_version(draft) or "v1")
    channel.request_review(task_id)
    events.append("review_started")
    raw_review = reviewer_fn(draft)
    review, contract_error = action_contract(raw_review if isinstance(raw_review, dict) else None)
    budget.charge("review")
    events.append("review_decision")
    (out_dir / "review_raw.json").write_text(
        json.dumps(raw_review if isinstance(raw_review, dict) else {"raw": raw_review}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "review_action.json").write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    envelope = None
    if contract_error == "ok" and review:
        envelope = mailbox.emit(review, artifact_before_hash=shared["sha256"], spec_version=private["spec_version"])
        events.append("review_emitted")
        if mutate_fn:
            mutate_fn(mailbox)
        mailbox.deliver(drop=drop)
        events.append("review_dropped" if drop else "review_delivered")
    inbox_payload = mailbox.read() if contract_error == "ok" and envelope is not None else None
    delivered = inbox_payload is not None
    if drop:
        review_for_builder = None
        delivered = False
    elif skip_inbox:
        review_for_builder = None
    else:
        review_for_builder = inbox_payload
    final_prompt = executor_prompt(draft, review_for_builder)
    final_raw = revise_fn(final_prompt, review_for_builder) or ""
    final = parse_source(final_raw)
    budget.charge("builder_final")
    after = out_dir / "artifact_after.py"
    channel.write_artifact(task_id=task_id, role="executor", kind="final", path=str(after), content=final)
    events.append("submitted")
    reviewer_write = channel.write_artifact(
        task_id=task_id, role="reviewer", kind="final", path=str(out_dir / "stolen.py"), content="x"
    )
    env_write = channel.write_artifact(
        task_id=task_id, role="environment", kind="final", path=str(after), content="ENVIRONMENT_REWRITE = 1\n"
    )
    builder_private = channel.read_private(task_id, "executor")
    disk_final = after.read_text(encoding="utf-8") if after.is_file() else ""
    hidden_in_prompt = []
    first_prompt = str(shared.get("draft_prompt") or "")
    for text in (first_prompt, final_prompt, json.dumps(review_for_builder) if review_for_builder else ""):
        if any(marker in text for marker in ORACLE_FILE_MARKERS):
            hidden_in_prompt.append("oracle_filename")
    (out_dir / "payload_trace.json").write_text(json.dumps(mailbox.trace(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "events": events,
        "draft": draft,
        "final": disk_final,
        "draft_path": str(before),
        "final_path": str(after),
        "review": review,
        "review_for_executor": review_for_builder,
        "review_emitted": envelope is not None,
        "review_delivered": delivered,
        "reviewer_ran": True,
        "executor_saw_review": review_for_builder is not None,
        "drop_inbox_empty": (track != "drop") or (len(mailbox.inbox) == 0 and review_for_builder is None),
        "contract_ok": contract_error == "ok",
        "contract_error": contract_error,
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "track": track,
        "shared_draft_sha256": shared["sha256"],
        "leak_on_first_brief": list(shared.get("leak_on_first_brief") or []),
        "draft_prompt_sha256": shared.get("draft_prompt_sha256"),
        "first_prompt": first_prompt,
        "final_prompt": final_prompt,
        "hidden_in_prompt": hidden_in_prompt,
        "reviewer_write": reviewer_write,
        "environment_write": env_write,
        "executor_private": builder_private,
        "builder_private": builder_private,
        "payload_trace": mailbox.trace(),
        "mailbox": mailbox,
        "environment_rewrote": after.is_file() and "ENVIRONMENT_REWRITE" in after.read_text(encoding="utf-8"),
        "executor_read_payload": (not skip_inbox) and review_for_builder is not None and not drop,
        "private_present": True,
        "initial_artifact_valid": bool((draft or "").strip()),
        "reviewer_id": reviewer_id,
    }
