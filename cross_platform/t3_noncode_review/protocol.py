"""Frozen task semantics, prompts and contracts for non-code T3 review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

PROTOCOL = "gaworld-benchmark-t3-noncode-review-v1"
ROOT = Path(__file__).resolve().parent
TASK_IDS = (
    "t3nc_clinic_cooling_shift_001",
    "t3nc_library_evening_hours_001",
    "t3nc_foodbank_delivery_001",
)
VARIANTS = ("verified_support", "verified_conflict")
ROLES = ("proposer", "reviewer", "executor")


def load_tasks() -> list[dict[str, Any]]:
    payload = yaml.safe_load((ROOT / "tasks.yaml").read_text(encoding="utf-8"))
    tasks = [dict(item) for item in payload["tasks"]]
    if tuple(str(task["id"]) for task in tasks) != TASK_IDS:
        raise ValueError("T3 non-code task order changed")
    return tasks


def evidence_for(task: dict[str, Any], variant: str) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant}")
    return dict(task["private_evidence"][variant])


def failing_criteria(
    task: dict[str, Any], evidence: dict[str, Any]
) -> list[str]:
    values = dict(evidence["values"])
    failed: list[str] = []
    for criterion in task["criteria"]:
        observed = values[str(criterion["evidence_field"])]
        required = criterion["required"]
        operator = str(criterion["operator"])
        passed = observed == required if operator == "eq" else observed >= required
        if not passed:
            failed.append(str(criterion["criterion_id"]))
    return failed


def expected_review(task: dict[str, Any], variant: str) -> dict[str, Any]:
    evidence = evidence_for(task, variant)
    failed = failing_criteria(task, evidence)
    return {
        "proposal_id": str(task["proposal_id"]),
        "decision": "reject" if failed else "approve",
        "evidence_ids": [str(item) for item in evidence["evidence_ids"]],
        "failing_criteria": failed,
        "reason_code": (
            "hard_constraint_conflict" if failed else "all_constraints_satisfied"
        ),
    }


def expected_executor(
    task: dict[str, Any], delivered_review: dict[str, Any] | None
) -> dict[str, Any]:
    if not delivered_review:
        return {
            "adopted": False,
            "final_state": dict(task["baseline_state"]),
            "disposition": "kept_without_review",
            "review_id": None,
            "reason_code": "no_delivered_review",
        }
    approved = delivered_review.get("decision") == "approve"
    return {
        "adopted": approved,
        "final_state": dict(
            task["proposed_state"] if approved else task["baseline_state"]
        ),
        "disposition": "adopted" if approved else "kept_after_reject",
        "review_id": str(delivered_review["review_id"]),
        "reason_code": (
            "approved_review_applied" if approved else "rejected_review_preserved_baseline"
        ),
    }


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def proposer_prompt(task: dict[str, Any]) -> str:
    return _dump(
        {
            "protocol": PROTOCOL,
            "role": "proposer",
            "instruction": (
                "Return exactly one JSON object matching response_schema. "
                "Copy proposal_id and proposed_state exactly; add no fields."
            ),
            "public_brief": str(task["public_brief"]),
            "baseline_state": dict(task["baseline_state"]),
            "registered_candidate": {
                "proposal_id": str(task["proposal_id"]),
                "proposed_state": dict(task["proposed_state"]),
            },
            "response_schema": {
                "proposal_id": "string",
                "proposed_state": "object",
                "reason_code": "registered_candidate_submitted",
            },
        }
    )


def reviewer_prompt(
    task: dict[str, Any],
    proposal: dict[str, Any],
    private_evidence: dict[str, Any],
) -> str:
    return _dump(
        {
            "protocol": PROTOCOL,
            "role": "reviewer",
            "instruction": (
                "Return exactly one JSON object matching response_schema. "
                "Approve only if every registered criterion passes; otherwise reject."
            ),
            "proposal": proposal,
            "criteria": [dict(item) for item in task["criteria"]],
            "private_verified_evidence": private_evidence,
            "rules": [
                "Evaluate every criterion against private_verified_evidence.values.",
                "For eq require equality; for gte require observed >= required.",
                "failing_criteria must list exactly the failed criterion_id values in registered order.",
                "evidence_ids must copy the registered private evidence IDs in order.",
            ],
            "response_schema": {
                "proposal_id": "string",
                "decision": "approve|reject",
                "evidence_ids": "array[string]",
                "failing_criteria": "array[string]",
                "reason_code": "all_constraints_satisfied|hard_constraint_conflict",
            },
        }
    )


def executor_prompt(
    task: dict[str, Any],
    proposal: dict[str, Any],
    delivered_review: dict[str, Any] | None,
) -> str:
    return _dump(
        {
            "protocol": PROTOCOL,
            "role": "executor",
            "instruction": (
                "Return exactly one JSON object matching response_schema. "
                "A delivered approving review adopts the candidate; a rejection or "
                "missing review preserves the baseline. Add no fields."
            ),
            "baseline_state": dict(task["baseline_state"]),
            "registered_candidate": proposal,
            "delivered_review": delivered_review,
            "execution_rules": [
                "approve with matching proposal_id -> adopted=true and final_state=proposed_state",
                "reject -> adopted=false and final_state=baseline_state",
                "missing review -> adopted=false and final_state=baseline_state",
                "copy delivered review_id, or null when no review exists",
            ],
            "response_schema": {
                "adopted": "boolean",
                "final_state": "object",
                "disposition": "adopted|kept_after_reject|kept_without_review",
                "review_id": "string|null",
                "reason_code": (
                    "approved_review_applied|rejected_review_preserved_baseline|"
                    "no_delivered_review"
                ),
            },
        }
    )


def proposer_validator(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {"proposal_id", "proposed_state", "reason_code"}
    if set(payload) != expected:
        errors.append(f"keys_must_equal:{sorted(expected)}")
    if not isinstance(payload.get("proposal_id"), str):
        errors.append("proposal_id_must_be_string")
    if not isinstance(payload.get("proposed_state"), dict):
        errors.append("proposed_state_must_be_object")
    if payload.get("reason_code") != "registered_candidate_submitted":
        errors.append("invalid_proposer_reason_code")
    return errors


def reviewer_validator(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "proposal_id",
        "decision",
        "evidence_ids",
        "failing_criteria",
        "reason_code",
    }
    if set(payload) != expected:
        errors.append(f"keys_must_equal:{sorted(expected)}")
    if not isinstance(payload.get("proposal_id"), str):
        errors.append("proposal_id_must_be_string")
    if payload.get("decision") not in {"approve", "reject"}:
        errors.append("decision_not_allowed")
    for field in ("evidence_ids", "failing_criteria"):
        value = payload.get(field)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            errors.append(f"{field}_must_be_string_array")
    if payload.get("reason_code") not in {
        "all_constraints_satisfied",
        "hard_constraint_conflict",
    }:
        errors.append("invalid_reviewer_reason_code")
    return errors


def executor_validator(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "adopted",
        "final_state",
        "disposition",
        "review_id",
        "reason_code",
    }
    if set(payload) != expected:
        errors.append(f"keys_must_equal:{sorted(expected)}")
    if not isinstance(payload.get("adopted"), bool):
        errors.append("adopted_must_be_boolean")
    if not isinstance(payload.get("final_state"), dict):
        errors.append("final_state_must_be_object")
    if payload.get("disposition") not in {
        "adopted",
        "kept_after_reject",
        "kept_without_review",
    }:
        errors.append("disposition_not_allowed")
    if payload.get("review_id") is not None and not isinstance(
        payload.get("review_id"), str
    ):
        errors.append("review_id_must_be_string_or_null")
    if payload.get("reason_code") not in {
        "approved_review_applied",
        "rejected_review_preserved_baseline",
        "no_delivered_review",
    }:
        errors.append("invalid_executor_reason_code")
    return errors


__all__ = [
    "PROTOCOL",
    "ROLES",
    "TASK_IDS",
    "VARIANTS",
    "evidence_for",
    "executor_prompt",
    "executor_validator",
    "expected_executor",
    "expected_review",
    "failing_criteria",
    "load_tasks",
    "proposer_prompt",
    "proposer_validator",
    "reviewer_prompt",
    "reviewer_validator",
]
