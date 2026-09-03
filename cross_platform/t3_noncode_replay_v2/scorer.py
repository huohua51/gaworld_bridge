"""Separate reviewer quality from platform replay fidelity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cross_platform.t3_noncode_replay_v2.protocol import (
    expected_executor,
    oracle_shared_review,
    payload_sha256,
)

SCORER_VERSION = "cross-platform-t3-noncode-shared-replay-scorer-v2"
WORKFLOW_ID = "cross_platform_t3_noncode_shared_replay_v2"


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file() or target.stat().st_size == 0:
        return []
    return [
        json.loads(line)
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def score_replay(
    *,
    task: dict[str, Any],
    variant: str,
    sample: dict[str, Any],
    loop: dict[str, Any],
) -> dict[str, Any]:
    shared = sample.get("shared_review")
    expected_shared = oracle_shared_review(task, variant)
    sample_valid = bool(sample.get("response_ok") and isinstance(shared, dict))
    reviewer_oracle_correct = bool(sample_valid and shared == expected_shared)
    platform_rows = _read_jsonl(str(loop["trace_path"]))
    trace_parseable = bool(platform_rows)
    payload_exact = bool(sample_valid and loop.get("delivered_review") == shared)
    payload_hash_exact = bool(
        sample_valid
        and loop.get("ingress_review_sha256") == payload_sha256(shared)
        and loop.get("delivered_review_sha256") == payload_sha256(shared)
    )
    expected_from_sample = expected_executor(
        task, dict(shared) if isinstance(shared, dict) else None
    )
    expected_from_oracle = expected_executor(task, expected_shared)
    transition_exact = loop.get("executor_output") == expected_from_sample
    oracle_final_exact = loop.get("executor_output") == expected_from_oracle
    role_boundaries = bool(
        loop.get("private_evidence_readers") == ["reviewer"]
        and loop.get("state_writers") == ["executor"]
    )
    transport_evaluable = sample_valid
    transport_pass = bool(
        transport_evaluable
        and trace_parseable
        and loop.get("proposal_delivered")
        and loop.get("review_delivery_verified")
        and loop.get("review_adoption_verified")
        and loop.get("final_submission_verified")
        and payload_exact
        and payload_hash_exact
        and transition_exact
        and role_boundaries
    )
    joint_full_pass = bool(
        sample_valid
        and reviewer_oracle_correct
        and transport_pass
        and oracle_final_exact
    )
    checks = [
        ("reviewer_sample_invalid", sample_valid),
        ("reviewer_oracle_incorrect", reviewer_oracle_correct),
        ("platform_trace_missing", trace_parseable),
        ("review_not_delivered", bool(loop.get("review_delivery_verified"))),
        ("payload_changed_in_transport", payload_exact and payload_hash_exact),
        ("review_not_adopted", bool(loop.get("review_adoption_verified"))),
        ("role_boundary_violation", role_boundaries),
        ("executor_transition_incorrect", transition_exact),
        ("final_submission_missing", bool(loop.get("final_submission_verified"))),
        ("oracle_final_state_incorrect", oracle_final_exact),
    ]
    first_error = next((name for name, passed in checks if not passed), "none")
    return {
        "workflow_id": WORKFLOW_ID,
        "run_id": str(loop["run_id"]),
        "task_id": str(task["id"]),
        "variant": variant,
        "platform": str(loop["platform"]),
        "measurement_valid": trace_parseable,
        "reviewer_sample_valid": sample_valid,
        "reviewer_oracle_correct": reviewer_oracle_correct,
        "transport_evaluable": transport_evaluable,
        "platform_transport_pass": transport_pass if transport_evaluable else None,
        "joint_full_pass": int(joint_full_pass),
        "full_pass": int(joint_full_pass),
        "ranking_eligible": False,
        "first_error": first_error,
        "criteria": {
            "platform_trace_parseable": trace_parseable,
            "shared_payload_exact": payload_exact,
            "shared_payload_hash_exact": payload_hash_exact,
            "deterministic_transition_exact": transition_exact,
            "oracle_final_state_exact": oracle_final_exact,
            "role_boundaries_enforced": role_boundaries,
        },
        "sample": sample,
        "process_profile": {
            "expected_shared_review": expected_shared,
            "ingress_review": loop.get("ingress_review"),
            "delivered_review": loop.get("delivered_review"),
            "executor_output": loop.get("executor_output"),
            "expected_executor_from_sample": expected_from_sample,
            "expected_executor_from_oracle": expected_from_oracle,
        },
        "evidence": {
            "model_evidence_id": sample.get("evidence_id"),
            "model_trace_path": sample.get("model_trace_path"),
            "platform_trace_path": loop.get("trace_path"),
            "ingress_review_sha256": loop.get("ingress_review_sha256"),
            "delivered_review_sha256": loop.get("delivered_review_sha256"),
        },
        "platform_evidence": {
            key: value
            for key, value in loop.items()
            if key
            in {
                "denials",
                "events",
                "native_event_attempts",
                "native_flow_count",
                "onesim_event_flow_path",
                "onesim_receipt_path",
                "verified_receipts",
            }
        },
    }


__all__ = ["SCORER_VERSION", "WORKFLOW_ID", "score_replay"]
