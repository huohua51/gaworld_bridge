"""N1 scoring. Hidden oracle is the expected keep/revise, not a file rewrite."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_n1.contract import KEEP, REVISE
from v0_first_batch.schema import CriterionResult, GateResult, compose


def expected_action(task: dict, variant: str, track: str) -> dict[str, Any]:
    oracle = json.loads(task["oracle"].read_text(encoding="utf-8"))
    if variant == "control":
        return dict(oracle["control"])
    if track == "drop":
        return dict(oracle["intervention_dropped"])
    return dict(oracle["intervention_delivered"])


def first_error(*, variant: str, track: str, contract_ok: bool, extractable: bool, action: dict, task: dict, delivered: bool) -> str:
    if not extractable:
        return "fields_not_extractable"
    if not contract_ok:
        return "decision_contract_invalid"
    if variant == "control" and action.get("action") == REVISE:
        return "false_positive_revision"
    if variant == "intervention" and track != "drop" and action.get("action") != REVISE:
        return "true_revision_missed"
    if variant == "intervention" and track == "drop":
        return "message_not_delivered"
    if variant == "intervention" and action.get("action") == REVISE:
        if action.get("target") != task["target"] or action.get("value") != task["intervention_value"]:
            return "wrong_revision_value"
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
    action = loop.get("decision") or {}
    want = expected_action(task, variant, track)
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    source_ok = loop.get("source_error") == "ok"
    relay_ok = loop.get("relay_error") == "ok"
    contract_ok = bool(loop.get("contract_ok"))
    delivered = bool(loop.get("executor_saw_message"))
    peek_blocked = (loop.get("peek_source") or {}).get("reason") == "unauthorized_private_read" and (
        loop.get("peek_verifier") or {}
    ).get("reason") == "unauthorized_private_read"
    drop_isolated = True if track != "drop" else not delivered and not loop.get("drop_dm_leaks")
    action_match = action.get("action") == want.get("action")
    if want.get("action") == REVISE:
        action_match = action_match and action.get("target") == want.get("target") and action.get("value") == want.get("value")
    if track == "drop" and variant == "intervention":
        conditioned = False
    else:
        conditioned = bool(contract_ok and action_match and (variant == "control" or delivered))
    r0 = (
        bool(loop.get("budget_valid"))
        and extractable
        and source_ok
        and relay_ok
        and peek_blocked
        and bool(loop.get("relay_ran"))
        and drop_isolated
        and not loop.get("leak_on_source_control")
        and not loop.get("oracle_in_prompt")
    )
    err = first_error(
        variant=variant,
        track=track,
        contract_ok=contract_ok,
        extractable=extractable and source_ok and relay_ok,
        action=action,
        task=task,
        delivered=delivered,
    )
    if conditioned:
        err = "none"
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0"),
            GateResult("budget_valid", bool(loop.get("budget_valid")), layer="R0"),
            GateResult("fields_extractable", extractable and source_ok and relay_ok, layer="R0"),
            GateResult("source_private_isolated", peek_blocked, layer="R0"),
            GateResult("relay_ran", bool(loop.get("relay_ran")), layer="R0"),
            GateResult("drop_isolated", drop_isolated, layer="R0"),
            GateResult("oracle_not_in_prompts", not loop.get("oracle_in_prompt"), layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[GateResult("decision_exists", bool(action), layer="R1")],
        criteria=[
            CriterionResult(
                criterion_id="action_correct",
                layer="R2",
                scorer="n1_oracle",
                evaluable=True,
                score=1.0 if action_match else 0.0,
                passed=action_match,
                critical=False,
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="n1_delivery",
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
            "action_correct": action_match,
            "oracle_conditioned_fullpass": conditioned,
            "relay_ran": bool(loop.get("relay_ran")),
            "executor_saw_message": delivered,
            "budget_calls": (loop.get("budget") or {}).get("calls"),
            "budget_kinds": (loop.get("budget") or {}).get("kinds"),
            "false_positive_revision": variant == "control" and action.get("action") == REVISE,
            "true_revision": variant == "intervention" and action.get("action") == REVISE and action.get("value") == task["intervention_value"],
            "first_error": err,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell
