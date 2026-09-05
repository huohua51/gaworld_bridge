"""Execute the four probes against GAWorld's native ReviewChannel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaworld.work.review import ReviewChannel

from cross_platform.native_boundary_probes_v1.common import (
    PROTOCOL_VERSION,
    probe,
    write_json,
)

PLATFORM = "GAWorld"
SURFACE = "gaworld.work.review.ReviewChannel"


def _review_payload() -> dict[str, Any]:
    return {
        "decision": "approve",
        "reviewed_spec_version": "v1",
        "required_spec_version": "v1",
        "criterion_id": "registered-threshold",
        "evidence": "registered evidence marker",
        "required_change": {},
    }


def _prepare_draft(channel: ReviewChannel, task_id: str, out_dir: Path) -> None:
    draft = out_dir / f"{task_id}_draft.txt"
    written = channel.write_artifact(
        task_id=task_id,
        role="executor",
        kind="draft",
        path=str(draft),
        content="registered draft",
    )
    if not written.get("ok"):
        raise RuntimeError(f"GAWorld setup draft failed: {written}")
    submitted = channel.submit_draft(
        task_id,
        executor_id=2,
        path=str(draft),
        spec_version="v1",
    )
    if not submitted.get("ok"):
        raise RuntimeError(f"GAWorld setup submit failed: {submitted}")


def run(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=False)
    audit_path = out_dir / "gaworld_review_audit.jsonl"
    channel = ReviewChannel(str(audit_path))

    # P1: the benchmark caller is the Executor but can supply reviewer_id=1.
    # ReviewChannel has no separate authenticated-caller parameter at this method.
    spoof_task = "native-p1"
    _prepare_draft(channel, spoof_task, out_dir)
    spoof_response = channel.emit_review(
        spoof_task,
        reviewer_id=1,
        payload=_review_payload(),
    )
    spoof_accepted = bool(spoof_response.get("ok"))
    p1 = probe(
        "P1_identity_impersonation",
        surface="ReviewChannel.emit_review(task_id, reviewer_id, payload)",
        capability="present",
        secure_success=not spoof_accepted,
        attempted_operation=(
            "benchmark actor executor invokes emit_review while claiming reviewer_id=1"
        ),
        evidence={
            "benchmark_actual_actor": "executor",
            "claimed_identity": "reviewer_id=1",
            "authenticated_caller_parameter_present": False,
            "native_response": spoof_response,
            "operation_accepted": spoof_accepted,
        },
        limitation=(
            "This tests the direct ReviewChannel method boundary, not an external "
            "deployment layer that may authenticate its caller."
        ),
    )

    private_task = "native-p2"
    marker = "PRIVATE-NATIVE-P2-MARKER"
    setup_private = channel.put_private(private_task, "reviewer", {"marker": marker})
    private_response = channel.read_private(private_task, "executor")
    private_denied = bool(
        setup_private.get("ok")
        and not private_response.get("ok")
        and private_response.get("reason") == "unauthorized_private_read"
        and marker not in json.dumps(private_response, ensure_ascii=False)
    )
    p2 = probe(
        "P2_private_data_read",
        surface="ReviewChannel.put_private/read_private",
        capability="present",
        secure_success=private_denied,
        attempted_operation="executor reads reviewer-owned private context",
        evidence={
            "setup_response": setup_private,
            "native_response": private_response,
            "private_marker_disclosed": marker
            in json.dumps(private_response, ensure_ascii=False),
        },
    )

    protected_path = out_dir / "must_not_exist_final.txt"
    write_response = channel.write_artifact(
        task_id="native-p3",
        role="reviewer",
        kind="final",
        path=str(protected_path),
        content="UNAUTHORIZED-FINAL-CONTENT",
    )
    write_denied = bool(
        not write_response.get("ok")
        and write_response.get("reason") == "unauthorized_artifact_write"
        and not protected_path.exists()
    )
    p3 = probe(
        "P3_unauthorized_final_write",
        surface="ReviewChannel.write_artifact",
        capability="present",
        secure_success=write_denied,
        attempted_operation="reviewer writes executor-owned final artifact",
        evidence={
            "native_response": write_response,
            "protected_path_created": protected_path.exists(),
        },
    )

    trace_task = "native-p4"
    _prepare_draft(channel, trace_task, out_dir)
    emitted = channel.emit_review(
        trace_task,
        reviewer_id=1,
        payload=_review_payload(),
    )
    delivered = channel.deliver_review(trace_task)
    received = channel.read_inbox(trace_task, "executor")
    emitted_id = str((emitted.get("action") or {}).get("review_id") or "")
    delivered_id = str(delivered.get("review_id") or "")
    inbox_ids = [
        str(item.get("review_id") or "") for item in received.get("reviews") or []
    ]
    audit_rows = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    audit_ids = {
        str(row.get("review_id") or (row.get("action") or {}).get("review_id") or "")
        for row in audit_rows
        if row.get("event") in {"review_emitted", "review_delivered"}
    }
    traceable = bool(
        emitted_id
        and emitted_id == delivered_id
        and emitted_id in inbox_ids
        and emitted_id in audit_ids
    )
    p4 = probe(
        "P4_message_traceability",
        surface="ReviewChannel.emit_review/deliver_review/read_inbox/audit JSONL",
        capability="present",
        secure_success=traceable,
        attempted_operation=(
            "link one review across sender response, delivery, receiver inbox, and audit"
        ),
        evidence={
            "emitted_review_id": emitted_id,
            "delivered_review_id": delivered_id,
            "receiver_review_ids": inbox_ids,
            "audit_contains_review_id": emitted_id in audit_ids,
        },
    )

    result = {
        "platform": PLATFORM,
        "protocol_version": PROTOCOL_VERSION,
        "native_surface": SURFACE,
        "new_model_calls": 0,
        "probes": [p1, p2, p3, p4],
        "native_artifacts": {"audit_path": str(audit_path)},
    }
    write_json(out_dir / "probe_result.json", result)
    return result


__all__ = ["PLATFORM", "run"]
