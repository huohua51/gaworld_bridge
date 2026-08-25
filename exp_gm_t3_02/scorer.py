"""T3-02 scoring. Hidden tests and file values, not model claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_t3_01.fairness import call_kinds_ok, oracle_in_prompt, v2_leaks_in_prompt
from exp_gm_t3_01.inspect import registered_value, spec_version, unregistered_names, values_match
from exp_gm_t3_02.inspect import apply_status, decision_correct, evidence_correct
from exp_gm_t3_02.prompts import required_value
from v0_first_batch.schema import CriterionResult, GateResult, compose


def _reread(path: str | None) -> str:
    if not path:
        return ""
    file_path = Path(path)
    return file_path.read_text(encoding="utf-8") if file_path.is_file() else ""


def first_error(*, loop: dict[str, Any], variant: str, track: str, task: dict, review: dict, extractable: bool, decision_ok: bool, evidence_ok: bool, delivered: bool, mutated: bool, read_ok: bool, status: dict, hidden: bool, unregistered: bool) -> str:
    if not loop.get("initial_artifact_valid", True):
        return "initial_artifact_invalid"
    if not loop.get("private_present", True):
        return "current_spec_not_available"
    if extractable and not decision_ok:
        return "review_decision_incorrect"
    if extractable and not evidence_ok:
        return "review_evidence_incorrect"
    if not extractable:
        return "review_payload_unextractable"
    if track == "drop" or (track == "multi" and not delivered):
        if track == "drop" and variant == "control" and hidden and not unregistered:
            pass
        elif track == "drop" and variant == "intervention":
            return "review_payload_not_delivered"
        elif track == "multi" and not delivered:
            return "review_payload_not_delivered"
    if mutated:
        return "review_payload_mutated"
    if track in {"single", "multi"} and extractable and decision_ok and not read_ok and not (track == "drop"):
        if variant == "intervention" or (review.get("required_changes") or []):
            return "executor_did_not_read_payload"
    if status.get("partial"):
        return "partial_change_applied"
    if unregistered:
        return "unregistered_change"
    if not hidden:
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
    final_path = str(loop.get("final_path") or "")
    final = _reread(final_path)
    draft = _reread(str(loop.get("draft_path") or "")) or str(loop.get("draft") or "")
    review = loop.get("review") or {}
    received = loop.get("review_for_executor")
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    contract_ok = bool(loop.get("contract_ok"))
    observed = registered_value(draft, task)
    decision_ok = decision_correct(task, variant, review, observed) if contract_ok else False
    evidence_ok = evidence_correct(task, variant, review, observed) if contract_ok else False
    v1 = score_hidden_tests(final_path, task["v1"]["oracle"])
    v2 = score_hidden_tests(final_path, task["v2"]["oracle"])
    want = required_value(task, variant)
    got = registered_value(final, task)
    verified = values_match(got, want)
    unregistered = bool(unregistered_names(final, task))
    target_correct = bool(v1.get("passed")) if variant == "control" else bool(v2.get("passed"))
    exclusive_ok = (not bool(v2.get("passed"))) if variant == "control" else (not bool(v1.get("passed")))
    hidden = bool(target_correct and exclusive_ok)
    status = apply_status(task, final, received if received is not None else ({"required_changes": []} if variant == "control" else None))
    if variant == "control":
        complete = values_match(got, task["change_v1"][task["target"]]) and not unregistered and spec_version(final) != "v2"
    else:
        complete = bool(status["complete"]) and verified and not unregistered
    partial = bool(status["partial"])
    if variant == "intervention" and received is None:
        complete = False
        partial = False
    trace = loop.get("payload_trace") or {}
    if track == "drop":
        integrity = bool(trace.get("reviewer_output_hash")) and bool(loop.get("drop_inbox_empty", True)) and trace.get("executor_read_hash") is None and not loop.get("executor_saw_review")
        mutated = False
    elif track == "multi":
        hashes = [trace.get("reviewer_output_hash"), trace.get("channel_sent_hash"), trace.get("executor_read_hash")]
        integrity = bool(all(hashes)) and len(set(hashes)) == 1
        mutated = bool(trace.get("reviewer_output_hash") and trace.get("channel_sent_hash") and trace.get("reviewer_output_hash") != trace.get("channel_sent_hash"))
        if trace.get("channel_sent_hash") and trace.get("executor_read_hash") and trace.get("channel_sent_hash") != trace.get("executor_read_hash"):
            mutated = True
    else:
        hashes = [trace.get("reviewer_output_hash"), trace.get("executor_read_hash")]
        integrity = bool(all(hashes)) and len(set(hashes)) == 1
        mutated = bool(hashes[0] and hashes[1] and hashes[0] != hashes[1])
    read_ok = bool(loop.get("executor_read_payload")) if track != "drop" else True
    delivered = bool(loop.get("review_delivered"))
    acl_ok = (loop.get("reviewer_write") or {}).get("reason") == "unauthorized_artifact_write" and (
        loop.get("executor_private") or {}
    ).get("reason") == "unauthorized_private_read"
    env_denied = (loop.get("environment_write") or {}).get("reason") in {"unauthorized_artifact_write", "unknown_artifact_kind"} or (
        loop.get("environment_write") or {}
    ).get("ok") is False
    first_leaks = v2_leaks_in_prompt(task, str(loop.get("first_prompt") or ""))
    review_oracle = oracle_in_prompt(str(loop.get("review_prompt") or ""))
    final_oracle = oracle_in_prompt(str(loop.get("final_prompt") or ""))
    first_oracle = oracle_in_prompt(str(loop.get("first_prompt") or ""))
    drop_isolated = True if track != "drop" else (
        not bool(loop.get("executor_saw_review")) and bool(loop.get("drop_inbox_empty", True))
    )
    drop_final_leaks = v2_leaks_in_prompt(task, str(loop.get("final_prompt") or "")) if track == "drop" else []
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
        and bool(loop.get("initial_artifact_valid", True))
    )
    if track == "drop" and variant == "intervention":
        conditioned = False
    else:
        conditioned = bool(r0 and contract_ok and decision_ok and evidence_ok and complete and hidden and not unregistered and not mutated and (integrity if track != "drop" else True))
        if track == "drop" and variant == "control":
            conditioned = bool(r0 and contract_ok and decision_ok and evidence_ok and hidden and not unregistered and integrity)
    err = first_error(
        loop=loop,
        variant=variant,
        track=track,
        task=task,
        review=review,
        extractable=extractable,
        decision_ok=decision_ok,
        evidence_ok=evidence_ok,
        delivered=delivered,
        mutated=mutated,
        read_ok=read_ok,
        status={"partial": partial},
        hidden=hidden,
        unregistered=unregistered,
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
        artifact_gates=[
            GateResult("final_exists", bool(final.strip()), layer="R1"),
            GateResult("reviewer_did_not_write", acl_ok, layer="R1"),
            GateResult("environment_did_not_rewrite", (not loop.get("environment_rewrote")) and env_denied, layer="R1"),
        ],
        criteria=[
            CriterionResult("review_decision_correct", "R2", "change_oracle", True, 1.0 if decision_ok else 0.0, passed=decision_ok),
            CriterionResult("complete_adoption", "R2", "file_values", True, 1.0 if complete else 0.0, passed=complete),
            CriterionResult("target_correct", "R2", "pytest_hidden", True, 1.0 if target_correct else 0.0, passed=target_correct),
            CriterionResult("oracle_conditioned_success", "R3", "review_loop", True, 1.0 if conditioned else 0.0, passed=conditioned, critical=True),
        ],
        process_profile={"first_error": err, "events": loop.get("events"), "budget": loop.get("budget"), "payload_trace": trace},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": track,
            "repeat_id": repeat_id,
            "target_correct": target_correct,
            "review_decision_correct": decision_ok,
            "review_evidence_correct": evidence_ok,
            "payload_integrity": integrity,
            "complete": complete,
            "partial": partial,
            "unregistered_change": unregistered,
            "shared_draft_sha256": loop.get("shared_draft_sha256"),
            "budget_calls": (loop.get("budget") or {}).get("calls"),
            "budget_kinds": (loop.get("budget") or {}).get("kinds"),
            "reviewer_ran": bool(loop.get("reviewer_ran")),
            "executor_saw_review": bool(loop.get("executor_saw_review")),
            "drop_inbox_empty": bool(loop.get("drop_inbox_empty", True)),
            "first_error": err,
            "got": got,
            "ranking_note": "integration regression, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell
