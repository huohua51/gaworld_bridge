"""T3-01 scoring. Hidden tests decide adoption, not claimed patches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_t3_01.contracts.review_action import APPROVE, REVISE
from exp_gm_t3_01.fairness import call_kinds_ok, oracle_in_prompt, v2_leaks_in_prompt
from exp_gm_t3_01.inspect import declared_patch, registered_value, spec_version, unregistered_names, values_match
from v0_first_batch.schema import CriterionResult, GateResult, compose


def review_decision_correct(variant: str, review: dict[str, Any], task: dict) -> bool:
    if variant == "control":
        return review.get("action") == APPROVE and "target" not in review and "required_value" not in review
    return (
        review.get("action") == REVISE
        and review.get("target") == task["target"]
        and values_match(review.get("required_value"), task["change_v2"][task["target"]])
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
    extractable: bool,
) -> str:
    if not extractable:
        return "fields_not_extractable"
    if not contract_ok:
        return "review_contract_invalid"
    if variant == "control" and review.get("action") == REVISE:
        return "false_positive_revision"
    if variant == "intervention" and review.get("action") == APPROVE:
        return "true_revision_missed"
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
    review = loop.get("review") or {}
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    contract_ok = bool(loop.get("contract_ok"))
    want = task["change_v1"][task["target"]] if variant == "control" else task["change_v2"][task["target"]]
    got = registered_value(final, task)
    verified = values_match(got, want)
    declared = declared_patch(final)
    unregistered = bool(unregistered_names(final, task))
    version_only = spec_version(final) == "v2" and values_match(got, task["change_v1"][task["target"]])
    target_correct = bool(v1.get("passed")) if variant == "control" else bool(v2.get("passed"))
    exclusive_ok = (not bool(v2.get("passed"))) if variant == "control" else (not bool(v1.get("passed")))
    advice_ok = review_decision_correct(variant, review, task) if contract_ok else False
    acl_ok = (loop.get("reviewer_write") or {}).get("reason") == "unauthorized_artifact_write" and (
        loop.get("executor_private") or loop.get("builder_private") or {}
    ).get("reason") == "unauthorized_private_read"
    first_leaks = v2_leaks_in_prompt(task, str(loop.get("first_prompt") or ""))
    review_oracle = oracle_in_prompt(str(loop.get("review_prompt") or ""))
    final_oracle = oracle_in_prompt(str(loop.get("final_prompt") or loop.get("first_prompt") or ""))
    first_oracle = oracle_in_prompt(str(loop.get("first_prompt") or ""))
    drop_isolated = True if track != "drop" else (
        not bool(loop.get("executor_saw_review")) and bool(loop.get("drop_inbox_empty", True))
    )
    drop_final_leaks = []
    if track == "drop" and loop.get("final_prompt"):
        drop_final_leaks = v2_leaks_in_prompt(task, str(loop.get("final_prompt")))
    three_calls = call_kinds_ok(list(((loop.get("budget") or {}).get("kinds") or [])))
    r0 = (
        bool(loop.get("budget_valid"))
        and three_calls
        and extractable
        and acl_ok
        and bool(loop.get("final_path"))
        and not loop.get("leak_on_first_brief")
        and not first_leaks
        and not drop_final_leaks
        and not first_oracle
        and not review_oracle
        and not final_oracle
        and not loop.get("hidden_in_prompt")
        and bool(loop.get("shared_draft_sha256"))
        and bool(loop.get("reviewer_ran"))
        and drop_isolated
    )
    if track == "drop" and variant == "intervention":
        conditioned = False
    elif variant == "control":
        conditioned = bool(r0 and contract_ok and advice_ok and target_correct and exclusive_ok and verified and not unregistered)
    else:
        conditioned = bool(
            r0 and contract_ok and advice_ok and verified and target_correct and exclusive_ok and not unregistered and not version_only
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
        extractable=extractable,
    )
    if conditioned:
        err = "none"
    if loop.get("final_path"):
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
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("no_v2_leak_on_draft", not bool(loop.get("leak_on_first_brief")) and not first_leaks, layer="R0"),
            GateResult("shared_draft_present", bool(loop.get("shared_draft_sha256")), layer="R0"),
            GateResult("three_calls", three_calls, layer="R0"),
            GateResult("reviewer_ran", bool(loop.get("reviewer_ran")), layer="R0"),
            GateResult("drop_executor_isolated", drop_isolated and not drop_final_leaks, layer="R0"),
            GateResult("oracle_not_in_prompts", not first_oracle and not review_oracle and not final_oracle, layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
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
            "contract_rejected": bool(loop.get("contract_rejected")),
            "budget_calls": (loop.get("budget") or {}).get("calls"),
            "budget_kinds": (loop.get("budget") or {}).get("kinds"),
            "reviewer_ran": bool(loop.get("reviewer_ran")),
            "executor_saw_review": bool(loop.get("executor_saw_review")),
            "drop_inbox_empty": bool(loop.get("drop_inbox_empty", True)),
            "false_positive_revision": variant == "control" and review.get("action") == REVISE,
            "true_revision": variant == "intervention" and advice_ok,
            "first_error": err,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell
