"""Score AgentSociety transport separately from its native identity boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cross_platform.t3_noncode_replay_v2.protocol import (
    expected_executor,
    oracle_shared_review,
    payload_sha256,
)

SCORER_VERSION = "cross-platform-t3-noncode-agentsociety-extension-scorer-v1"
WORKFLOW_ID = "cross_platform_t3_noncode_shared_replay_v3_agentsociety"


def _trace_rows(path: str) -> list[dict[str, Any]]:
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
    review = sample.get("shared_review")
    sample_valid = bool(sample.get("response_ok") and isinstance(review, dict))
    oracle_review = oracle_shared_review(task, variant)
    reviewer_oracle_correct = bool(sample_valid and review == oracle_review)
    trace_parseable = bool(_trace_rows(str(loop["trace_path"])))
    payload_exact = bool(sample_valid and loop.get("delivered_review") == review)
    payload_hash_exact = bool(
        sample_valid
        and loop.get("ingress_review_sha256") == payload_sha256(review)
        and loop.get("delivered_review_sha256") == payload_sha256(review)
    )
    expected_from_sample = expected_executor(
        task, dict(review) if isinstance(review, dict) else None
    )
    expected_from_oracle = expected_executor(task, oracle_review)
    transition_exact = loop.get("executor_output") == expected_from_sample
    oracle_final_exact = loop.get("executor_output") == expected_from_oracle
    identity_probe = dict(loop.get("identity_binding_probe") or {})
    native_acl = bool(identity_probe.get("native_acl_enforced_at_tested_boundary"))
    transport_evaluable = sample_valid
    transport_pass = bool(
        transport_evaluable
        and trace_parseable
        and loop.get("proposal_delivered")
        and loop.get("review_delivery_verified")
        and loop.get("review_adoption_verified")
        and loop.get("final_submission_verified")
        and loop.get("native_sender_receiver_verified")
        and payload_exact
        and payload_hash_exact
        and transition_exact
    )
    functional_full_pass = bool(
        sample_valid
        and reviewer_oracle_correct
        and transport_pass
        and oracle_final_exact
    )
    strict_role_isolated_full_pass = bool(functional_full_pass and native_acl)
    checks = [
        ("reviewer_sample_invalid", sample_valid),
        ("reviewer_oracle_incorrect", reviewer_oracle_correct),
        ("platform_trace_missing", trace_parseable),
        ("review_not_delivered", bool(loop.get("review_delivery_verified"))),
        ("payload_changed_in_transport", payload_exact and payload_hash_exact),
        (
            "native_sender_receiver_mismatch",
            bool(loop.get("native_sender_receiver_verified")),
        ),
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
        "payload_transport_pass": transport_pass if transport_evaluable else None,
        "functional_full_pass": int(functional_full_pass),
        "strict_role_isolated_full_pass": int(strict_role_isolated_full_pass),
        "ranking_eligible": False,
        "first_error": first_error,
        "criteria": {
            "platform_trace_parseable": trace_parseable,
            "shared_payload_exact": payload_exact,
            "shared_payload_hash_exact": payload_hash_exact,
            "native_sender_receiver_verified": bool(
                loop.get("native_sender_receiver_verified")
            ),
            "deterministic_transition_exact": transition_exact,
            "oracle_final_state_exact": oracle_final_exact,
            "native_acl_enforced_at_tested_boundary": native_acl,
            "native_message_id_observable_at_receive_boundary": bool(
                loop.get("native_message_id_observable_at_receive_boundary")
            ),
        },
        "process_profile": {
            "expected_shared_review": oracle_review,
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
            "platform_tool_history_path": loop.get("tool_history_path"),
            "ingress_review_sha256": loop.get("ingress_review_sha256"),
            "delivered_review_sha256": loop.get("delivered_review_sha256"),
        },
        "capability_evidence": {
            "runtime": {
                "environment_version": loop.get("environment_version"),
                "package_dunder_version": loop.get("package_dunder_version"),
                "execution_surface": loop.get("execution_surface"),
                "offline_runtime": loop.get("offline_runtime"),
            },
            "identity_binding_probe": identity_probe,
            "native_tool_calls": loop.get("native_tool_calls"),
            "verified_receipts": loop.get("verified_receipts"),
        },
    }


__all__ = ["SCORER_VERSION", "WORKFLOW_ID", "score_replay"]
