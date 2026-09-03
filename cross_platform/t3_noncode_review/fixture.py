"""Deterministic oracle-shaped client for pre-live T3 calibration."""

from __future__ import annotations

import json
from typing import Any

from benchmark_core.model_runner import CallableModelClient


def _evaluate(criteria: list[dict[str, Any]], evidence: dict[str, Any]) -> list[str]:
    values = evidence["values"]
    failed: list[str] = []
    for criterion in criteria:
        observed = values[criterion["evidence_field"]]
        required = criterion["required"]
        passed = (
            observed == required
            if criterion["operator"] == "eq"
            else observed >= required
        )
        if not passed:
            failed.append(criterion["criterion_id"])
    return failed


def _handler(prompt: str, task: str, agent_id: str | None) -> str:
    payload = json.loads(prompt)
    role = payload["role"]
    if role == "proposer":
        candidate = payload["registered_candidate"]
        response = {
            "proposal_id": candidate["proposal_id"],
            "proposed_state": candidate["proposed_state"],
            "reason_code": "registered_candidate_submitted",
        }
    elif role == "reviewer":
        evidence = payload["private_verified_evidence"]
        failed = _evaluate(payload["criteria"], evidence)
        response = {
            "proposal_id": payload["proposal"]["proposal_id"],
            "decision": "reject" if failed else "approve",
            "evidence_ids": evidence["evidence_ids"],
            "failing_criteria": failed,
            "reason_code": (
                "hard_constraint_conflict"
                if failed
                else "all_constraints_satisfied"
            ),
        }
    elif role == "executor":
        review = payload["delivered_review"]
        approved = bool(review and review["decision"] == "approve")
        response = {
            "adopted": approved,
            "final_state": (
                payload["registered_candidate"]["proposed_state"]
                if approved
                else payload["baseline_state"]
            ),
            "disposition": (
                "adopted"
                if approved
                else "kept_after_reject"
                if review
                else "kept_without_review"
            ),
            "review_id": review["review_id"] if review else None,
            "reason_code": (
                "approved_review_applied"
                if approved
                else "rejected_review_preserved_baseline"
                if review
                else "no_delivered_review"
            ),
        }
    else:
        raise ValueError(f"unknown fixture role: {role}")
    return json.dumps(response, ensure_ascii=False, separators=(",", ":"))


def oracle_fixture_client() -> CallableModelClient:
    return CallableModelClient(
        _handler,
        provider="offline-t3-noncode-oracle-fixture",
        model_version="offline-t3-noncode-oracle-fixture-v1",
        live=False,
    )


__all__ = ["oracle_fixture_client"]
