"""Run one non-code T3 cell through GAWorld's native ReviewChannel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaworld.work.review import ReviewChannel

from benchmark_core.model_runner import RecordedModelRunner, StructuredModelResponse
from cross_platform.t3_noncode_review.protocol import (
    evidence_for,
    executor_prompt,
    executor_validator,
    proposer_prompt,
    proposer_validator,
    reviewer_prompt,
    reviewer_validator,
)


def _call(
    runner: RecordedModelRunner,
    *,
    role: str,
    prompt: str,
    validator: Any,
) -> StructuredModelResponse:
    return runner.call_json(
        prompt,
        task="benchmark_t3_noncode_review",
        agent_id=role,
        validator=validator,
    )


def run_cell(
    task: dict[str, Any],
    variant: str,
    out_dir: Path,
    model_runner: RecordedModelRunner,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "gaworld_review_trace.jsonl"
    proposal_path = out_dir / "proposal.json"
    final_path = out_dir / "final_state.json"
    for path in (trace_path, proposal_path, final_path):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite evidence: {path}")

    channel = ReviewChannel(str(trace_path))
    task_id = str(task["id"])
    private_evidence = evidence_for(task, variant)
    private_put = channel.put_private(task_id, "reviewer", private_evidence)

    proposer_response = _call(
        model_runner,
        role="proposer",
        prompt=proposer_prompt(task),
        validator=proposer_validator,
    )
    proposal = dict(proposer_response.parsed) if proposer_response.ok else {}
    proposal_write = channel.write_artifact(
        task_id=task_id,
        role="executor",
        kind="draft",
        path=str(proposal_path),
        content=json.dumps(proposal, ensure_ascii=False, sort_keys=True),
    )
    draft_submit = channel.submit_draft(
        task_id,
        executor_id=1,
        path=str(proposal_path),
        spec_version="v1",
    )
    review_request = channel.request_review(task_id)
    private_read = channel.read_private(task_id, "reviewer")
    visible_private = dict(private_read.get("payload") or {})

    reviewer_response = _call(
        model_runner,
        role="reviewer",
        prompt=reviewer_prompt(task, proposal, visible_private),
        validator=reviewer_validator,
    )
    review_output = dict(reviewer_response.parsed) if reviewer_response.ok else {}
    emitted: dict[str, Any] = {"ok": False, "reason": "model_response_invalid"}
    delivered: dict[str, Any] = {"ok": False, "reason": "review_not_emitted"}
    common_delivered: dict[str, Any] | None = None
    adopted: dict[str, Any] = {"ok": False, "reason": "review_not_delivered"}
    if reviewer_response.ok:
        channel_payload = {
            "decision": (
                "approve" if review_output["decision"] == "approve" else "revise"
            ),
            "reviewed_spec_version": "v1",
            "required_spec_version": "v2",
            "criterion_id": "registered_hard_constraints",
            "evidence": json.dumps(
                review_output,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "required_change": (
                {}
                if review_output["decision"] == "approve"
                else {"disposition": "reject_proposal_keep_baseline"}
            ),
        }
        emitted = channel.emit_review(task_id, reviewer_id=2, payload=channel_payload)
        if emitted.get("ok"):
            delivered = channel.deliver_review(task_id)
            inbox = channel.read_inbox(task_id, "executor")
            reviews = list(inbox.get("reviews") or [])
            if reviews:
                carrier = dict(reviews[-1])
                common_delivered = json.loads(str(carrier["evidence"]))
                common_delivered["review_id"] = str(carrier["review_id"])
                adopted = channel.adopt_review(
                    task_id,
                    str(carrier["review_id"]),
                    current_spec_version="v1",
                )

    executor_response = _call(
        model_runner,
        role="executor",
        prompt=executor_prompt(task, proposal, common_delivered),
        validator=executor_validator,
    )
    executor_output = dict(executor_response.parsed) if executor_response.ok else {}
    final_write = channel.write_artifact(
        task_id=task_id,
        role="executor",
        kind="final",
        path=str(final_path),
        content=json.dumps(executor_output, ensure_ascii=False, sort_keys=True),
    )

    reviewer_write_probe = channel.write_artifact(
        task_id=task_id,
        role="reviewer",
        kind="final",
        path=str(out_dir / "unauthorized_reviewer_state.json"),
        content="{}",
    )
    executor_private_probe = channel.read_private(task_id, "executor")
    responses = [proposer_response, reviewer_response, executor_response]
    return {
        "platform": "GAWorld",
        "environment_version": "gaworld-review-channel-v2",
        "trace_version": "gaworld-review-and-model-jsonl-t3-noncode-v1",
        "trace_path": str(trace_path),
        "model_trace_path": str(model_runner.path),
        "proposal_path": str(proposal_path),
        "final_path": str(final_path),
        "proposal": proposal,
        "review_output": review_output,
        "delivered_review": common_delivered,
        "executor_output": executor_output,
        "final_state": dict(executor_output.get("final_state") or {}),
        "events": channel.event_names(),
        "denials": channel.denials(),
        "private_put": private_put,
        "private_read": private_read,
        "proposal_write": proposal_write,
        "draft_submit": draft_submit,
        "review_request": review_request,
        "review_emitted": emitted,
        "review_delivered": delivered,
        "review_adopted": adopted,
        "final_write": final_write,
        "reviewer_write_probe": reviewer_write_probe,
        "executor_private_probe": executor_private_probe,
        "proposal_delivered": bool(review_request.get("ok")),
        "review_delivery_verified": common_delivered is not None,
        "review_adoption_verified": bool(adopted.get("ok")),
        "final_submission_verified": bool(final_write.get("ok")),
        "private_evidence_readers": ["reviewer"] if private_read.get("ok") else [],
        "state_writers": ["executor"] if final_write.get("ok") else [],
        "model_call_evidence_ids": [response.evidence_id for response in responses],
        "model_summary": model_runner.summary(),
    }


__all__ = ["run_cell"]
