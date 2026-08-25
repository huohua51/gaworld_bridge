"""Full-workflow scoring. TargetCorrect and FullPass stay separate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_05c.contract import validate_action
from exp_gm_05c.inspect import declared_patch, registered_value, spec_version, unregistered_names, values_match
from v0_first_batch.schema import CriterionResult, GateResult, compose


def _path_ok(path: Any, task: dict) -> bool:
    text = str(path or "")
    return text in {task["path"], task["symbol"], task["criterion_id"]}


def review_decision_correct(variant: str, review: dict[str, Any], task: dict, draft: str) -> bool:
    got = registered_value(draft, task)
    if variant == "control":
        return (
            review.get("decision") == "approve"
            and review.get("required_change") is None
            and not review.get("mismatches")
        )
    change = review.get("required_change") or {}
    if not isinstance(change, dict):
        return False
    new_value = change.get("new_value", change.get(task["path"]))
    return (
        review.get("decision") == "revise"
        and bool(review.get("mismatches"))
        and _path_ok(change.get("path") or task["path"], task)
        and values_match(new_value, task["change_v2"][task["path"]])
        and not values_match(got, task["change_v2"][task["path"]])
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
    version_only: bool,
    contract_ok: bool,
) -> str:
    if not contract_ok:
        return "model_contract_failure"
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
        if declared or version_only:
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
    if "contract_ok" in loop:
        contract_ok = bool(loop.get("contract_ok"))
    else:
        contract_ok = validate_action(review).ok if review else False
    want = task["change_v1"][task["path"]] if variant == "control" else task["change_v2"][task["path"]]
    got = registered_value(final, task)
    verified = values_match(got, want)
    declared = declared_patch(final)
    unregistered = bool(unregistered_names(final, task))
    version_only = spec_version(final) == "v2" and values_match(got, task["change_v1"][task["path"]])
    target_correct = bool(v1.get("passed")) if variant == "control" else bool(v2.get("passed"))
    exclusive_ok = (not bool(v2.get("passed"))) if variant == "control" else (not bool(v1.get("passed")))
    advice_ok = review_decision_correct(variant, review, task, draft) if contract_ok else False
    parseable = contract_ok
    acl_ok = (loop.get("reviewer_write") or {}).get("reason") == "unauthorized_artifact_write" and (
        loop.get("executor_private") or loop.get("builder_private") or {}
    ).get("reason") == "unauthorized_private_read"
    r0 = (
        bool(loop.get("budget_valid"))
        and parseable
        and acl_ok
        and bool(loop.get("final_path"))
        and not loop.get("leak_on_first_brief")
        and not loop.get("hidden_in_prompt")
        and bool(loop.get("shared_draft_sha256"))
    )
    if track == "drop" and variant == "intervention":
        conditioned = False
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
        version_only=version_only,
        contract_ok=contract_ok,
    )
    if conditioned:
        err = "none"
    Path(loop["final_path"]).parent.joinpath("hidden_test_result.json").write_text(
        json.dumps({"v1": v1, "v2": v2, "target_correct": target_correct, "exclusive_ok": exclusive_ok}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0"),
            GateResult("budget_valid", bool(loop.get("budget_valid")), layer="R0"),
            GateResult("fields_extractable", parseable, layer="R0"),
            GateResult("no_v2_leak_on_draft", not bool(loop.get("leak_on_first_brief")), layer="R0"),
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
            "target_correct": target_correct,
            "oracle_conditioned_fullpass": conditioned,
            "review_decision_correct": advice_ok,
            "declared_patch_adoption": declared,
            "verified_patch_adoption": bool(verified) if variant == "intervention" else False,
            "acknowledgement_execution_gap": bool(declared) and not verified,
            "unregistered_change": unregistered,
            "shared_draft_sha256": loop.get("shared_draft_sha256"),
            "v2_published_after_draft": bool(loop.get("v2_published_after_draft")),
            "parser_repair_used": bool((loop.get("contract") or {}).get("parser_repair_used")),
            "contract_retry_used": bool(loop.get("contract_retry_used")),
            "contract_retry_success": bool(loop.get("contract_retry_success")),
            "total_model_calls": loop.get("total_model_calls"),
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
