"""Reviewer-only cell loop. No Executor, no artifact rewrite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_04c.roles import render_source
from exp_gm_04e.roles import facts_for, true_revision
from exp_gm_04e.tasks import private_payload
from gaworld.work.artifact_facts import artifact_hash, nack_payload, verify_review

ReviewerFn = Callable[[str, dict[str, Any], str], dict[str, Any]]


def run_reviewer_cell(
    *,
    task: dict,
    variant: str,
    protocol: str,
    task_id: str,
    out_dir: Path,
    reviewer_fn: ReviewerFn,
    max_calls: int = 2,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    source = render_source(task, "v1")
    (out_dir / "draft_main.py").write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
    expected_version = "v1" if variant == "control" else "v2"
    private = private_payload(task, expected_version, protocol=protocol)
    facts = facts_for(task, source)
    current_hash = artifact_hash(source)
    events: list[str] = ["draft_fixed", "facts_extracted"]
    calls = 0
    extra = ""
    review: dict[str, Any] = {}
    verify: dict[str, Any] = {"ok": False, "reason": "review_not_emitted"}

    while calls < max_calls:
        calls += 1
        events.append(f"reviewer_call_{calls}")
        review = reviewer_fn(source, private, extra) or {}
        if protocol == "evidence_bound":
            verify = verify_review(review, facts=facts, private=private, current_hash=current_hash)
            if verify.get("ok"):
                events.append("review_verified")
                break
            events.append(verify.get("reason") or "review_evidence_not_bound")
            extra = json.dumps(nack_payload(), ensure_ascii=False)
            continue
        parseable = review.get("decision") in {"approve", "revise"}
        verify = {"ok": parseable, "reason": "ok" if parseable else "review_contract_invalid"}
        if parseable:
            events.append("review_parsed")
            break
        events.append("review_contract_invalid")
        extra = "输出不是合法审核 JSON。可再输出一次。没有新的事实或标准。"

    grounded = bool(protocol != "evidence_bound" or verify.get("ok"))
    fp = variant == "control" and review.get("decision") == "revise"
    if protocol == "evidence_bound" and variant == "control" and not verify.get("ok") and review.get("decision") == "revise":
        fp = True
    true_rev = variant == "intervention" and true_revision(
        review, task, private, protocol=protocol, grounded=grounded if protocol == "evidence_bound" else True
    )
    return {
        "events": events,
        "source": source,
        "facts": [item.to_public_dict() for item in facts],
        "private_keys": sorted((private.get("required_change") or {}).keys()),
        "review": review,
        "verify": verify,
        "reviewer_calls": calls,
        "expected_decision": "approve" if variant == "control" else "revise",
        "false_positive_revision": fp,
        "true_revision": true_rev,
        "grounded": grounded,
        "first_error": _first_error(protocol, variant, review, verify, true_rev, fp, grounded),
    }


def _first_error(protocol: str, variant: str, review: dict, verify: dict, true_rev: bool, fp: bool, grounded: bool) -> str:
    if protocol == "evidence_bound" and not verify.get("ok"):
        return str(verify.get("reason") or "review_evidence_not_bound")
    if not review.get("decision"):
        return "review_not_emitted"
    if variant == "control" and fp:
        return "false_positive_revision"
    if variant == "intervention" and not true_rev:
        return "true_revision_missed"
    return "none"
