"""Evidence-first scoring for the paired non-code T3 review experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from benchmark_core.result import RunContext, compose_cell
from model_pilot.evidence import model_trace_evidence, read_jsonl
from v0_first_batch.schema import CriterionResult, GateResult

from cross_platform.t3_noncode_review.protocol import (
    ROLES,
    evidence_for,
    expected_executor,
    expected_review,
)

WORKFLOW_ID = "cross_platform_t3_noncode_review_v1"
SCORER_VERSION = "cross-platform-t3-noncode-review-scorer-v1"


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _prompt_payloads(requests: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for row in requests:
        role = str(row.get("agent_id") or "")
        try:
            parsed = json.loads(str(row.get("prompt") or ""))
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            payloads[role] = parsed
    return payloads


def _prompt_hashes(requests: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row.get("agent_id") or ""): str(row.get("prompt_sha256") or "")
        for row in requests
        if row.get("agent_id")
    }


def _platform_trace(path: str) -> tuple[list[dict[str, Any]], str]:
    try:
        rows = read_jsonl(path)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return [], f"{type(exc).__name__}:{exc}"
    return rows, "ok" if rows else "empty"


def _first_error(checks: list[tuple[str, bool]]) -> str:
    return next((name for name, passed in checks if not passed), "none")


def score_cell(
    *,
    task: dict[str, Any],
    variant: str,
    platform: str,
    run_id: str,
    loop: dict[str, Any],
    eval_mode_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Score one platform/task/variant cell without trusting adapter summaries."""

    model = model_trace_evidence(str(loop["model_trace_path"]))
    platform_rows, platform_trace_detail = _platform_trace(str(loop["trace_path"]))
    requests = list(model["requests"])
    request_roles = [str(row.get("agent_id") or "") for row in requests]
    prompt_payloads = _prompt_payloads(requests)
    prompt_hashes = _prompt_hashes(requests)
    evidence_ids = [str(item) for item in model["evidence_ids"] if item]

    expected_private = evidence_for(task, variant)
    reviewer_payload = prompt_payloads.get("reviewer", {})
    proposer_payload = prompt_payloads.get("proposer", {})
    executor_payload = prompt_payloads.get("executor", {})
    private_isolated = bool(
        reviewer_payload.get("private_verified_evidence") == expected_private
        and not _contains_key(proposer_payload, "private_verified_evidence")
        and not _contains_key(executor_payload, "private_verified_evidence")
        and not _contains_key(proposer_payload, "values")
        and not _contains_key(executor_payload, "values")
    )

    expected_proposal = {
        "proposal_id": str(task["proposal_id"]),
        "proposed_state": dict(task["proposed_state"]),
        "reason_code": "registered_candidate_submitted",
    }
    registered_review = expected_review(task, variant)
    expected_delivered = {
        **registered_review,
        "review_id": f"{task['id']}_r1",
    }
    delivered = loop.get("delivered_review")
    expected_execution = expected_executor(
        task, dict(delivered) if isinstance(delivered, dict) else None
    )
    oracle_execution = expected_executor(task, expected_delivered)

    proposal_ok = loop.get("proposal") == expected_proposal
    review_ok = loop.get("review_output") == registered_review
    delivered_review_ok = delivered == expected_delivered
    executor_compliance_ok = loop.get("executor_output") == expected_execution
    final_state_ok = loop.get("final_state") == oracle_execution["final_state"]
    adoption_effect_ok = bool(
        loop.get("executor_output", {}).get("adopted")
        == oracle_execution["adopted"]
        and loop.get("executor_output", {}).get("disposition")
        == oracle_execution["disposition"]
    )
    model_trace_complete = bool(
        model["trace_parseable"]
        and model["calls"] == 3
        and len(model["responses"]) == 3
        and request_roles == list(ROLES)
        and len(evidence_ids) == 3
    )
    role_boundaries_ok = bool(
        loop.get("private_evidence_readers") == ["reviewer"]
        and loop.get("state_writers") == ["executor"]
    )

    checks = [
        ("platform_trace_missing", bool(platform_rows)),
        ("model_trace_incomplete", model_trace_complete),
        ("model_response_invalid", bool(model["contract_ok"])),
        ("proposal_incorrect", proposal_ok),
        ("private_evidence_leak_or_missing", private_isolated),
        ("proposal_not_delivered", bool(loop.get("proposal_delivered"))),
        ("review_incorrect", review_ok),
        ("review_not_delivered", bool(loop.get("review_delivery_verified"))),
        ("delivered_review_incorrect", delivered_review_ok),
        ("review_not_adopted", bool(loop.get("review_adoption_verified"))),
        ("role_boundary_violation", role_boundaries_ok),
        ("executor_ignored_review", executor_compliance_ok),
        ("final_submission_missing", bool(loop.get("final_submission_verified"))),
        ("adoption_effect_incorrect", adoption_effect_ok),
        ("final_state_incorrect", final_state_ok),
    ]
    first_error = _first_error(checks)

    measurement_gates = [
        GateResult(
            "platform_trace_parseable",
            bool(platform_rows),
            detail=f"rows={len(platform_rows)};{platform_trace_detail}",
        ),
        GateResult(
            "model_trace_complete",
            model_trace_complete,
            detail=(
                f"requests={model['calls']};responses={len(model['responses'])};"
                f"roles={request_roles};evidence_ids={len(evidence_ids)}"
            ),
        ),
    ]
    artifact_gates = [
        GateResult(
            "model_responses_structured",
            bool(model["contract_ok"]),
            layer="R1",
            detail="ok" if model["contract_ok"] else ";".join(model["errors"]),
        ),
        GateResult(
            "proposal_and_review_delivered",
            bool(
                loop.get("proposal_delivered")
                and loop.get("review_delivery_verified")
                and delivered_review_ok
            ),
            layer="R1",
            detail=(
                f"proposal={bool(loop.get('proposal_delivered'))};"
                f"review={bool(loop.get('review_delivery_verified'))};"
                f"payload_exact={delivered_review_ok}"
            ),
        ),
        GateResult(
            "review_adopted_and_final_submitted",
            bool(
                loop.get("review_adoption_verified")
                and loop.get("final_submission_verified")
            ),
            layer="R1",
            detail=(
                f"adopted={bool(loop.get('review_adoption_verified'))};"
                f"submitted={bool(loop.get('final_submission_verified'))}"
            ),
        ),
        GateResult(
            "private_evidence_isolated",
            private_isolated,
            layer="R1",
            detail="reviewer-only prompt field and value visibility",
        ),
        GateResult(
            "role_boundaries_enforced",
            role_boundaries_ok,
            layer="R1",
            detail=(
                f"private_readers={loop.get('private_evidence_readers')};"
                f"state_writers={loop.get('state_writers')}"
            ),
        ),
    ]

    def criterion(
        criterion_id: str, passed: bool, scorer: str, detail: str
    ) -> CriterionResult:
        return CriterionResult(
            criterion_id=criterion_id,
            layer="R2",
            scorer=scorer,
            evaluable=True,
            score=float(passed),
            passed=passed,
            critical=True,
            evidence_ids=evidence_ids,
            detail=detail,
        )

    criteria = [
        criterion(
            "proposal_fidelity",
            proposal_ok,
            "exact_registered_candidate_match",
            f"expected={expected_proposal};actual={loop.get('proposal')}",
        ),
        criterion(
            "independent_review_correct",
            review_ok,
            "exact_oracle_review_match",
            f"expected={registered_review};actual={loop.get('review_output')}",
        ),
        criterion(
            "executor_review_compliance",
            executor_compliance_ok,
            "exact_delivered_review_transition",
            f"expected={expected_execution};actual={loop.get('executor_output')}",
        ),
        criterion(
            "adoption_effect_correct",
            adoption_effect_ok,
            "registered_support_conflict_effect",
            f"expected={oracle_execution};actual={loop.get('executor_output')}",
        ),
        criterion(
            "final_state_correct",
            final_state_ok,
            "exact_oracle_final_state_match",
            f"expected={oracle_execution['final_state']};actual={loop.get('final_state')}",
        ),
    ]

    context = RunContext(
        run_id=run_id,
        task_id=str(task["id"]),
        task_family="T3",
        mechanism_condition=platform,
        variant=variant,
        seed=0,
        track="full",
        model_version=str(model["model_version"]),
        temperature=float(model["temperature"]),
        budget={"calls_per_cell": 3},
        environment_version=str(loop["environment_version"]),
        trace_version=str(loop["trace_version"]),
        scorer_version=SCORER_VERSION,
        evidence_id=f"bundle:{run_id}",
    )
    cell = compose_cell(
        workflow_id=WORKFLOW_ID,
        context=context,
        eval_mode_evidence=eval_mode_evidence,
        measurement_gates=measurement_gates,
        artifact_gates=artifact_gates,
        criteria=criteria,
        process_profile={
            "proposal": loop.get("proposal"),
            "review": loop.get("review_output"),
            "delivered_review": delivered,
            "executor_output": loop.get("executor_output"),
            "expected_review": registered_review,
            "expected_executor": oracle_execution,
            "first_error": first_error,
        },
        extra={
            "platform": platform,
            "variant": variant,
            "task_title": str(task["title"]),
            "prompt_sha256_by_role": prompt_hashes,
            "role_outputs": {
                "proposer": loop.get("proposal"),
                "reviewer": loop.get("review_output"),
                "executor": loop.get("executor_output"),
            },
            "model_evidence_ids": evidence_ids,
            "platform_trace_path": str(loop["trace_path"]),
            "model_trace_path": str(loop["model_trace_path"]),
            "platform_evidence": {
                key: value
                for key, value in loop.items()
                if key
                in {
                    "onesim_receipt_path",
                    "onesim_event_flow_path",
                    "native_event_attempts",
                    "verified_receipts",
                    "native_flow_count",
                    "denials",
                }
            },
            "first_error": first_error,
        },
    )
    cell["ranking_eligible"] = False
    return cell


__all__ = ["SCORER_VERSION", "WORKFLOW_ID", "score_cell"]
