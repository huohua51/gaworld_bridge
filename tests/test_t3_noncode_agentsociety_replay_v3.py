from __future__ import annotations

from cross_platform.t3_noncode_replay_v2.protocol import (
    load_tasks,
    oracle_shared_review,
    payload_sha256,
)
from cross_platform.t3_noncode_replay_v3.agentsociety_replay import replay
from cross_platform.t3_noncode_replay_v3.scorer import score_replay


def test_agentsociety_shared_review_transport_and_capability_probe(tmp_path):
    task = load_tasks()[0]
    variant = "verified_support"
    review = oracle_shared_review(task, variant)
    sample = {
        "task_id": task["id"],
        "variant": variant,
        "response_ok": True,
        "evidence_id": "fixture:one",
        "model_trace_path": "fixture",
        "shared_review": review,
        "shared_review_sha256": payload_sha256(review),
    }

    loop = replay(task, variant, review, tmp_path / "cell")
    score = score_replay(task=task, variant=variant, sample=sample, loop=loop)

    assert loop["delivered_review"] == review
    assert loop["native_sender_receiver_verified"] is True
    assert loop["native_tool_calls"] == 4
    assert score["payload_transport_pass"] is True
    assert score["functional_full_pass"] == 1
    assert score["criteria"]["native_acl_enforced_at_tested_boundary"] is False
    assert (
        score["criteria"]["native_message_id_observable_at_receive_boundary"] is False
    )
    assert score["strict_role_isolated_full_pass"] == 0
    runtime = score["capability_evidence"]["runtime"]
    assert runtime["execution_surface"] == (
        "SimpleSocialSpace.send_message/receive_messages"
    )
    assert runtime["offline_runtime"] == {
        "credential_mode": "benchmark_sentinel_not_user_secret",
        "api_base": "http://127.0.0.1:9",
        "new_model_calls": 0,
    }


def test_invalid_reviewer_sample_is_not_attributed_to_platform(tmp_path):
    task = load_tasks()[0]
    variant = "verified_conflict"
    sample = {
        "task_id": task["id"],
        "variant": variant,
        "response_ok": False,
        "response_error": "provider_error:fixture",
        "evidence_id": "fixture:invalid",
        "model_trace_path": "fixture",
        "shared_review": None,
    }

    loop = replay(task, variant, None, tmp_path / "invalid")
    score = score_replay(task=task, variant=variant, sample=sample, loop=loop)

    assert score["measurement_valid"] is True
    assert score["transport_evaluable"] is False
    assert score["payload_transport_pass"] is None
    assert score["functional_full_pass"] == 0
    assert score["first_error"] == "reviewer_sample_invalid"
