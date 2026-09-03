"""Frozen shared-review sampling and replay semantics for T3 non-code v2."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from cross_platform.t3_noncode_review.protocol import (
    ROLES as V1_ROLES,
)
from cross_platform.t3_noncode_review.protocol import (
    TASK_IDS,
    VARIANTS,
    evidence_for,
    expected_executor,
    expected_review,
    load_tasks,
    reviewer_validator,
)
from cross_platform.t3_noncode_review.protocol import (
    reviewer_prompt as v1_reviewer_prompt,
)

PROTOCOL = "gaworld-benchmark-t3-noncode-shared-review-replay-v2"
PLATFORMS = ("GAWorld", "YuLan-OneSim")
CALIBRATION_CASES = (
    (TASK_IDS[0], "verified_support"),
    (TASK_IDS[0], "verified_conflict"),
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def registered_proposal(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": str(task["proposal_id"]),
        "proposed_state": dict(task["proposed_state"]),
        "reason_code": "registered_candidate_submitted",
    }


def reviewer_prompt(task: dict[str, Any], variant: str) -> str:
    """Reuse v1 task semantics while declaring the new sampling protocol."""

    payload = json.loads(
        v1_reviewer_prompt(
            task,
            registered_proposal(task),
            evidence_for(task, variant),
        )
    )
    payload["protocol"] = PROTOCOL
    payload["sampling_design"] = "one_reviewer_sample_shared_across_platforms"
    return canonical_json(payload)


def shared_review(
    task: dict[str, Any], reviewer_output: dict[str, Any]
) -> dict[str, Any]:
    return {
        **reviewer_output,
        "review_id": f"{task['id']}_r1",
    }


def oracle_shared_review(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return shared_review(task, expected_review(task, variant))


__all__ = [
    "CALIBRATION_CASES",
    "PLATFORMS",
    "PROTOCOL",
    "TASK_IDS",
    "V1_ROLES",
    "VARIANTS",
    "canonical_json",
    "evidence_for",
    "expected_executor",
    "expected_review",
    "load_tasks",
    "oracle_shared_review",
    "payload_sha256",
    "registered_proposal",
    "reviewer_prompt",
    "reviewer_validator",
    "shared_review",
]
