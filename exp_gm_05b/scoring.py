"""Direct TargetCorrect plus review-stage FullPass. partial_change_applied is not 'no adoption'."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_05b.inspect import declared_patch, registered_value, spec_version, unregistered_names, values_match
from v0_first_batch.schema import CriterionResult, GateResult, compose


def review_decision_correct(variant: str, review: dict[str, Any], task: dict, draft: str) -> bool:
    got = registered_value(draft, task)
    if variant == "control":
        return review.get("decision") == "approve" and (not review.get("required_change"))
    required = dict(task["change_v2"])
    change = dict(review.get("required_change") or {})
    return (
        review.get("decision") == "revise"
        and str(review.get("required_spec_version") or "") == "v2"
        and values_match(change.get(task["path"]), required.get(task["path"]))
        and not values_match(got, required.get(task["path"]))
    )


def evidence_grounded(variant: str, review: dict[str, Any], task: dict, draft: str) -> bool:
    return review_decision_correct(variant, review, task, draft) or (
        variant == "control" and review.get("decision") == "approve"
    )


def first_error(
    *,
    track: str,
    variant: str,
    review: dict[str, Any],
    advice_ok: bool,
    verified: bool,
    declared: bool,
    unregistered: bool,
    target_correct: bool,
    exclusive_ok: bool,
    delivered: bool,
) -> str:
    if track == "direct_final_spec":
        return "none" if target_correct else "direct_task_logic_failed"
    if review.get("decision") not in {"approve", "revise"}:
        return "true_revision_missed"
    if variant == "control" and review.get("decision") == "revise":
        return "false_positive_revision"
    if variant == "intervention" and not advice_ok:
        return "true_revision_missed"
    if track == "drop" and variant == "intervention":
        return "review_not_delivered"
    if track == "multi" and not delivered:
        return "review_not_delivered"
    if unregistered:
        return "unregistered_change"
    if variant == "intervention" and advice_ok and not verified:
        if declared:
            return "change_acknowledged_not_applied"
        return "required_change_not_read"
    if verified and not target_correct:
        return "partial_change_applied"
    if not target_correct or not exclusive_ok:
        return "final_hidden_test_failed"
    return "none"


def score_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    repeat_id: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    v1 = score_hidden_tests(loop.get("final_path"), task["v1"]["oracle"])
    v2 = score_hidden_tests(loop.get("final_path"), task["v2"]["oracle"])
    final = loop.get("final") or ""
    draft = loop.get("draft") or ""
    review = loop.get("review") or {}
    want = task["change_v1"][task["path"]] if variant == "control" else task["change_v2"][task["path"]]
    got = registered_value(final, task)
    verified = values_match(got, want)
    declared = declared_patch(final)
    unregistered = bool(unregistered_names(final, task))
    version_only = spec_version(final) == "v2" and values_match(got, task["change_v1"][task["path"]])
    target_correct = bool(v1.get("passed")) if variant == "control" else bool(v2.get("passed"))
    exclusive_ok = (not bool(v2.get("passed"))) if variant == "control" else (not bool(v1.get("passed")))
    advice_ok = True
    grounded = True
    if track != "direct_final_spec":
        advice_ok = review_decision_correct(variant, review, task, draft)
        grounded = evidence_grounded(variant, review, task, draft)
    parseable = track == "direct_final_spec" or review.get("decision") in {"approve", "revise"}
    acl_ok = True
    if track != "direct_final_spec":
        acl_ok = (loop.get("reviewer_write") or {}).get("reason") == "unauthorized_artifact_write" and (
            loop.get("executor_private") or {}
        ).get("reason") == "unauthorized_private_read"
    r0 = bool(loop.get("budget_valid")) and parseable and acl_ok and bool(loop.get("final_path"))
    if track == "drop" and variant == "intervention":
        conditioned = False
    elif track == "direct_final_spec":
        conditioned = bool(r0 and target_correct and exclusive_ok)
    elif variant == "control":
        conditioned = bool(r0 and advice_ok and target_correct and exclusive_ok and verified and not unregistered)
    else:
        conditioned = bool(
            r0 and advice_ok and verified and target_correct and exclusive_ok and not unregistered and not version_only
        )
    err = first_error(
        track=track,
        variant=variant,
        review=review,
        advice_ok=advice_ok,
        verified=verified,
        declared=declared,
        unregistered=unregistered,
        target_correct=target_correct,
        exclusive_ok=exclusive_ok,
        delivered=bool(loop.get("review_delivered")),
    )
    if version_only and track != "direct_final_spec" and variant == "intervention":
        err = "change_acknowledged_not_applied"
    if conditioned:
        err = "none"
    Path(loop["final_path"]).parent.joinpath("hidden_test_result.json").write_text(
        json.dumps({"v1": v1, "v2": v2, "target_correct": target_correct}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0"),
            GateResult("budget_valid", bool(loop.get("budget_valid")), layer="R0"),
            GateResult("fields_extractable", parseable, layer="R0"),
        ],
        artifact_gates=[GateResult("final_exists", bool((final or "").strip()), layer="R1")],
        criteria=[
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="pytest_hidden",
                evaluable=True,
                score=1.0 if target_correct else 0.0,
                passed=target_correct,
                critical=track == "direct_final_spec",
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="review_loop",
                evaluable=track != "direct_final_spec",
                score=1.0 if conditioned else 0.0,
                passed=conditioned,
                critical=track != "direct_final_spec",
            ),
        ],
        process_profile={"first_error": err, "events": loop.get("events"), "budget": loop.get("budget")},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": track,
            "repeat_id": repeat_id,
            "target_correct": target_correct,
            "oracle_conditioned_fullpass": conditioned if track != "direct_final_spec" else target_correct and exclusive_ok,
            "review_decision_correct": advice_ok if track != "direct_final_spec" else None,
            "evidence_grounding": grounded if track != "direct_final_spec" else None,
            "declared_patch_adoption": declared,
            "verified_patch_adoption": bool(verified) if variant == "intervention" else False,
            "acknowledgement_execution_gap": bool(declared) and not verified,
            "unregistered_change": unregistered,
            "first_error": err,
            "ranking_note": "calibration, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    extra = cell.get("extra") or {}
    extra["measurement_valid"] = bool(cell.get("measurement_valid"))
    cell["extra"] = extra
    Path(loop["final_path"]).parent.joinpath("cell_result.json").write_text(
        json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return cell
