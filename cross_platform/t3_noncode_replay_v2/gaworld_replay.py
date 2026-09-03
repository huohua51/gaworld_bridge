"""Replay one already-sampled review through GAWorld's ReviewChannel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaworld.work.review import ReviewChannel

from cross_platform.t3_noncode_replay_v2.protocol import (
    canonical_json,
    evidence_for,
    expected_executor,
    payload_sha256,
    registered_proposal,
)


def replay(
    task: dict[str, Any],
    variant: str,
    review: dict[str, Any] | None,
    out_dir: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    trace_path = out_dir / "gaworld_review_trace.jsonl"
    proposal_path = out_dir / "proposal.json"
    final_path = out_dir / "final_state.json"
    manifest_path = out_dir / "replay_manifest.json"

    channel = ReviewChannel(str(trace_path))
    task_id = str(task["id"])
    proposal = registered_proposal(task)
    private_put = channel.put_private(task_id, "reviewer", evidence_for(task, variant))
    proposal_write = channel.write_artifact(
        task_id=task_id,
        role="executor",
        kind="draft",
        path=str(proposal_path),
        content=canonical_json(proposal),
    )
    draft_submit = channel.submit_draft(
        task_id,
        executor_id=1,
        path=str(proposal_path),
        spec_version="v1",
    )
    review_request = channel.request_review(task_id)

    emitted: dict[str, Any] = {"ok": False, "reason": "shared_review_unavailable"}
    delivered: dict[str, Any] = {"ok": False, "reason": "review_not_emitted"}
    adopted: dict[str, Any] = {"ok": False, "reason": "review_not_delivered"}
    delivered_review: dict[str, Any] | None = None
    if review is not None:
        carrier = {
            "decision": "approve" if review["decision"] == "approve" else "revise",
            "reviewed_spec_version": "v1",
            "required_spec_version": "v2",
            "criterion_id": "registered_hard_constraints",
            "evidence": canonical_json(review),
            "required_change": (
                {}
                if review["decision"] == "approve"
                else {"disposition": "reject_proposal_keep_baseline"}
            ),
        }
        emitted = channel.emit_review(task_id, reviewer_id=2, payload=carrier)
        if emitted.get("ok"):
            delivered = channel.deliver_review(task_id)
            inbox = channel.read_inbox(task_id, "executor")
            reviews = list(inbox.get("reviews") or [])
            if reviews:
                native_review = dict(reviews[-1])
                delivered_review = json.loads(str(native_review["evidence"]))
                delivered_review["review_id"] = str(native_review["review_id"])
                adopted = channel.adopt_review(
                    task_id,
                    str(native_review["review_id"]),
                    current_spec_version="v1",
                )

    executor_output = expected_executor(task, delivered_review)
    final_write = channel.write_artifact(
        task_id=task_id,
        role="executor",
        kind="final",
        path=str(final_path),
        content=canonical_json(executor_output),
    )
    reviewer_write_probe = channel.write_artifact(
        task_id=task_id,
        role="reviewer",
        kind="final",
        path=str(out_dir / "unauthorized_reviewer_state.json"),
        content="{}",
    )
    executor_private_probe = channel.read_private(task_id, "executor")
    result = {
        "platform": "GAWorld",
        "environment_version": "gaworld-review-channel-v2",
        "trace_version": "shared-review-replay-v2",
        "trace_path": str(trace_path),
        "proposal_path": str(proposal_path),
        "final_path": str(final_path),
        "ingress_review": review,
        "ingress_review_sha256": payload_sha256(review),
        "delivered_review": delivered_review,
        "delivered_review_sha256": payload_sha256(delivered_review),
        "executor_output": executor_output,
        "proposal_delivered": bool(review_request.get("ok")),
        "review_delivery_verified": delivered_review is not None,
        "review_adoption_verified": bool(adopted.get("ok")),
        "final_submission_verified": bool(final_write.get("ok")),
        "payload_exact": delivered_review == review,
        "private_evidence_readers": ["reviewer"],
        "state_writers": ["executor"] if final_write.get("ok") else [],
        "events": channel.event_names(),
        "denials": channel.denials(),
        "private_put": private_put,
        "proposal_write": proposal_write,
        "draft_submit": draft_submit,
        "review_request": review_request,
        "review_emitted": emitted,
        "review_delivered": delivered,
        "review_adopted": adopted,
        "reviewer_write_probe": reviewer_write_probe,
        "executor_private_probe": executor_private_probe,
    }
    manifest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


__all__ = ["replay"]
