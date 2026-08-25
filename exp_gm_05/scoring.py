"""R0—R3 for equal-budget multi-agent value. FullPass is oracle-conditioned."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_05.inspect import declared_patch_ids, registered_value, spec_version, unregistered_names, values_match
from v0_first_batch.schema import CriterionResult, GateResult, compose


def review_decision_correct(variant: str, review: dict[str, Any], task: dict) -> bool:
    if variant == "control":
        return review.get("decision") == "approve"
    required = dict(task["change_v2"])
    got = dict(review.get("required_change") or {})
    return (
        review.get("decision") == "revise"
        and str(review.get("required_spec_version") or "") == "v2"
        and values_match(got.get(task["path"]), required.get(task["path"]))
    )


def first_error(
    *,
    track: str,
    variant: str,
    events: list[str],
    review: dict[str, Any],
    delivered: bool,
    advice_ok: bool,
    verified: bool,
    declared: bool,
    unregistered: bool,
    version_only: bool,
    wrong_value: bool,
    target_correct: bool,
    exclusive_ok: bool,
) -> str:
    if "requirement_available" not in events:
        return "requirement_not_seen"
    if "draft_created" not in events:
        return "hidden_test_failed"
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
    if variant == "intervention" and advice_ok and not verified:
        if declared or version_only:
            return "change_acknowledged_not_applied"
        if wrong_value:
            return "wrong_value_applied"
        return "required_change_not_read"
    if unregistered:
        return "unregistered_change"
    if not target_correct or not exclusive_ok:
        return "hidden_test_failed"
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
    got_final = registered_value(final, task)
    got_draft = registered_value(draft, task)
    want = task["change_v1"][task["path"]] if variant == "control" else task["change_v2"][task["path"]]
    verified = values_match(got_final, want)
    declared = declared_patch_ids(final)
    unregistered = bool(unregistered_names(final, task))
    version_only = spec_version(final) == "v2" and values_match(got_final, task["change_v1"][task["path"]])
    wrong_value = (
        got_final is not None
        and not values_match(got_final, got_draft)
        and not values_match(got_final, want)
    )
    advice_ok = review_decision_correct(variant, review, task)
    target_correct = bool(v1.get("passed")) if variant == "control" else bool(v2.get("passed"))
    exclusive_ok = (not bool(v2.get("passed"))) if variant == "control" else (not bool(v1.get("passed")))
    review_parseable = review.get("decision") in {"approve", "revise"}
    r0 = all(
        [
            bool(loop.get("budget_valid")),
            review_parseable,
            not loop.get("leak_on_first_brief"),
            not loop.get("hidden_in_prompt"),
            bool(loop.get("draft_path")),
            bool(loop.get("final_path")),
            (loop.get("reviewer_write") or {}).get("reason") == "unauthorized_artifact_write",
            (loop.get("executor_private") or {}).get("reason") == "unauthorized_private_read",
        ]
    )
    artifact_ok = bool(final.strip()) and "TODO" not in final

    if track == "drop" and variant == "intervention":
        conditioned = False
    elif track == "drop" and variant == "control":
        conditioned = bool(r0 and artifact_ok and target_correct and exclusive_ok and verified and not unregistered)
    elif variant == "control":
        conditioned = bool(
            r0 and artifact_ok and advice_ok and target_correct and exclusive_ok and verified and not unregistered and not declared
        )
    else:
        conditioned = bool(
            r0
            and artifact_ok
            and advice_ok
            and verified
            and target_correct
            and exclusive_ok
            and not unregistered
            and not version_only
            and not (declared and not verified)
        )

    err = first_error(
        track=track,
        variant=variant,
        events=list(loop.get("events") or []),
        review=review,
        delivered=bool(loop.get("review_delivered")),
        advice_ok=advice_ok,
        verified=verified,
        declared=declared,
        unregistered=unregistered,
        version_only=version_only,
        wrong_value=wrong_value,
        target_correct=target_correct,
        exclusive_ok=exclusive_ok,
    )
    if conditioned:
        err = "none"

    hidden_payload = {"v1": v1, "v2": v2, "target_correct": target_correct, "exclusive_ok": exclusive_ok}
    Path(loop["final_path"]).parent.joinpath("hidden_test_result.json").write_text(
        json.dumps(hidden_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0", detail="budget/parse/leak/acl"),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("budget_valid", bool(loop.get("budget_valid")), layer="R0"),
            GateResult("fields_extractable", review_parseable, layer="R0"),
        ],
        artifact_gates=[
            GateResult("draft_and_final", artifact_ok, layer="R1"),
            GateResult("reviewer_did_not_write", True, layer="R1"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="pytest_hidden",
                evaluable=True,
                score=1.0 if target_correct else 0.0,
                passed=target_correct,
                critical=False,
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="review_loop",
                evaluable=True,
                score=1.0 if conditioned else 0.0,
                passed=conditioned,
                critical=True,
            ),
        ],
        process_profile={"first_error": err, "events": loop.get("events"), "budget": loop.get("budget")},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": track,
            "repeat_id": repeat_id,
            "budget_valid": bool(loop.get("budget_valid")),
            "artifact_valid": artifact_ok,
            "target_correct": target_correct,
            "oracle_conditioned_fullpass": conditioned,
            "review_decision_correct": advice_ok,
            "declared_patch_adoption": declared,
            "verified_patch_adoption": bool(verified) if variant == "intervention" else False,
            "unregistered_change": unregistered,
            "first_error": err,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    extra = cell.get("extra") or {}
    extra["measurement_valid"] = bool(cell.get("measurement_valid"))
    extra["oracle_conditioned_fullpass"] = bool(cell.get("full_pass")) if cell.get("measurement_valid") else False
    cell["extra"] = extra
    Path(loop["final_path"]).parent.joinpath("cell_result.json").write_text(
        json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return cell
