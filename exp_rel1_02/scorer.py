"""Frozen REL1-v2 scorer."""

from __future__ import annotations

from typing import Any

from exp_rel1_02.loader import current_signals
from v0_first_batch.schema import CriterionResult, GateResult, compose

WORKFLOW_ID = "exp_rel1_02_registered_reliability"
SCORER_VERSION = "rel1-registered-reliability-v2.0"


def _trust_ok(model: dict[str, Any], message: dict[str, Any], want: dict[str, Any], phase: str) -> bool:
    return bool(
        model.get("trusted_source_id") == want[f"{phase}_source"]
        and model.get("trusted_state") == want[f"{phase}_state"]
        and model.get("evidence_row_ids") == want[f"{phase}_rows"]
        and message.get("trusted_person_id") == want[f"{phase}_source"]
        and message.get("trusted_state") == want[f"{phase}_state"]
    )


def _action_ok(action: dict[str, Any], message: dict[str, Any], task: dict[str, Any], want_value: str, version: str, phase: str) -> bool:
    return bool(
        action.get("action") == task["action"]
        and action.get("value") == want_value
        and action.get("evidence_message_id") == message.get("message_id")
        and action.get("adopted_trust_version") == version
        and action.get("round") == phase
    )


def _first_error(loop: dict[str, Any], task: dict[str, Any], want: dict[str, Any]) -> str:
    if not all(loop["model_ok"]):
        return "model_response_invalid"
    if loop["model_binding_attempt"]:
        return "model_attempted_platform_binding"
    if loop["observed_signals"] != current_signals(task):
        return "current_signal_not_relayed"
    if not _trust_ok(loop["formation_model"], loop["formation_message"] or {}, want, "formation"):
        return "formation_reliability_incorrect"
    if not _action_ok(loop["formation_action"], loop["formation_message"] or {}, task, want["formation_value"], "v1", "formation"):
        return "formation_action_incorrect"
    if not _trust_ok(loop["update_model"], loop["update_message"] or {}, want, "update"):
        return "latest_binding_update_incorrect"
    if not _action_ok(loop["update_action"], loop["update_message"] or {}, task, want["update_value"], "v2", "update"):
        return "update_action_incorrect"
    return "none"


def score_cell(task: dict[str, Any], variant: str, loop: dict[str, Any]) -> dict[str, Any]:
    want = task["oracle"][variant]
    formation_message = loop.get("formation_message") or {}
    update_message = loop.get("update_message") or {}
    structured = len(loop["model_ok"]) == 5 and all(loop["model_ok"])
    signals_ok = loop["observed_signals"] == current_signals(task)
    formation_trust = _trust_ok(loop["formation_model"], formation_message, want, "formation")
    update_trust = _trust_ok(loop["update_model"], update_message, want, "update")
    formation_action = _action_ok(
        loop["formation_action"], formation_message, task, want["formation_value"], "v1", "formation"
    )
    update_action = _action_ok(
        loop["update_action"], update_message, task, want["update_value"], "v2", "update"
    )
    adopted = bool(loop["formation_adopt"].get("ok") and loop["update_adopt"].get("ok"))
    error = _first_error(loop, task, want)
    result = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=f"rel1_v2_{task['id']}_{variant}_full_s0",
        measurement_gates=[
            GateResult("model_responses_structured", structured, layer="R0"),
            GateResult("fixed_five_call_budget", (loop["model_summary"] or {}).get("calls") == 5, layer="R0"),
            GateResult("model_did_not_issue_binding_ids", not loop["model_binding_attempt"], layer="R0"),
            GateResult("history_isolated_from_dispatcher", bool(loop["history_isolated"]), layer="R0"),
            GateResult("trust_updater_cannot_submit", bool(loop["updater_submit_denied"]), layer="R0"),
        ],
        artifact_gates=[
            GateResult("current_signals_delivered", bool(loop["delivered_current"].get("ok")), layer="R1"),
            GateResult("both_trust_messages_adopted", adopted, layer="R1"),
            GateResult("both_actions_bound", bool(loop["formation_action"] and loop["update_action"]), layer="R1"),
        ],
        criteria=[
            CriterionResult("observer_relay_faithful", "R2", "registered_signals", True, float(signals_ok), passed=signals_ok, critical=True),
            CriterionResult("formation_history_count_correct", "R2", "frozen_oracle", True, float(formation_trust), passed=formation_trust, critical=True),
            CriterionResult("formation_evidence_rows_correct", "R2", "row_ids", True, float(loop["formation_model"].get("evidence_row_ids") == want["formation_rows"]), passed=loop["formation_model"].get("evidence_row_ids") == want["formation_rows"], critical=True),
            CriterionResult("latest_row_binding_update_correct", "R2", "frozen_oracle", True, float(update_trust), passed=update_trust, critical=True),
            CriterionResult("update_evidence_latest_only", "R2", "row_ids", True, float(loop["update_model"].get("evidence_row_ids") == want["update_rows"]), passed=loop["update_model"].get("evidence_row_ids") == want["update_rows"], critical=True),
            CriterionResult("formation_action_platform_bound", "R2", "trust_ledger", True, float(formation_action), passed=formation_action, critical=True),
            CriterionResult("update_action_platform_bound", "R2", "trust_ledger", True, float(update_action), passed=update_action, critical=True),
        ],
        process_profile={"first_error": error, "events": loop["events"], "relationships": loop["relationships"]},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": "full",
            "seed": 0,
            "first_error": error,
            "formation_correct": formation_trust,
            "update_correct": update_trust,
            "formation_action_bound": formation_action,
            "update_action_bound": update_action,
            "latest_is_binding": True,
            "model_evidence_ids": loop["model_evidence_ids"],
            "got_formation": loop["formation_model"],
            "got_update": loop["update_model"],
            "got_formation_action": loop["formation_action"],
            "got_update_action": loop["update_action"],
            "want": want,
        },
    )
    result["ranking_eligible"] = False
    return result
