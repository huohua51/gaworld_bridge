"""Frozen REL1-v3 scorer."""

from __future__ import annotations

from typing import Any

from exp_rel1_03.loader import current_signals
from v0_first_batch.schema import CriterionResult, GateResult, compose

WORKFLOW_ID = "exp_rel1_03_phase_separated_reliability"
SCORER_VERSION = "rel1-phase-separated-v3.0"


def _action_ok(action: dict[str, Any], message: dict[str, Any], task: dict[str, Any], value: str, version: str, phase: str) -> bool:
    return bool(
        action.get("action") == task["action"]
        and action.get("value") == value
        and action.get("evidence_message_id") == message.get("message_id")
        and action.get("adopted_trust_version") == version
        and action.get("round") == phase
    )


def _first_error(loop: dict[str, Any], task: dict[str, Any], want: dict[str, Any]) -> str:
    formation = loop["formation_model"]
    update = loop["update_model"]
    if not all(loop["model_ok"]):
        return "model_response_invalid"
    if loop["model_binding_attempt"]:
        return "model_attempted_platform_binding"
    if loop["observed_signals"] != current_signals(task):
        return "current_signal_not_relayed"
    if formation.get("correct_counts") != want["formation_counts"]:
        return "formation_counts_incorrect"
    if formation.get("supporting_row_ids") != want["formation_support"]:
        return "formation_support_rows_incorrect"
    if formation.get("trusted_source_id") != want["formation_source"] or formation.get("trusted_state") != want["formation_state"]:
        return "formation_source_incorrect"
    if not _action_ok(loop["formation_action"], loop["formation_message"] or {}, task, want["formation_value"], "v1", "formation"):
        return "formation_action_incorrect"
    if update.get("trusted_source_id") != want["update_source"] or update.get("trusted_state") != want["update_state"]:
        return "latest_binding_source_incorrect"
    if update.get("evidence_row_ids") != want["update_rows"]:
        return "latest_binding_evidence_incorrect"
    if not _action_ok(loop["update_action"], loop["update_message"] or {}, task, want["update_value"], "v2", "update"):
        return "update_action_incorrect"
    return "none"


def score_cell(task: dict[str, Any], variant: str, loop: dict[str, Any]) -> dict[str, Any]:
    want = task["oracle"][variant]
    formation = loop["formation_model"]
    update = loop["update_model"]
    formation_message = loop.get("formation_message") or {}
    update_message = loop.get("update_message") or {}
    structured = len(loop["model_ok"]) == 5 and all(loop["model_ok"])
    signals_ok = loop["observed_signals"] == current_signals(task)
    counts_ok = formation.get("correct_counts") == want["formation_counts"]
    support_ok = formation.get("supporting_row_ids") == want["formation_support"]
    formation_source_ok = bool(
        formation.get("trusted_source_id") == want["formation_source"]
        and formation.get("trusted_state") == want["formation_state"]
        and formation_message.get("trusted_person_id") == want["formation_source"]
    )
    update_source_ok = bool(
        update.get("trusted_source_id") == want["update_source"]
        and update.get("trusted_state") == want["update_state"]
        and update_message.get("trusted_person_id") == want["update_source"]
    )
    update_evidence_ok = update.get("evidence_row_ids") == want["update_rows"]
    formation_action_ok = _action_ok(
        loop["formation_action"], formation_message, task, want["formation_value"], "v1", "formation"
    )
    update_action_ok = _action_ok(
        loop["update_action"], update_message, task, want["update_value"], "v2", "update"
    )
    adopted = bool(loop["formation_adopt"].get("ok") and loop["update_adopt"].get("ok"))
    error = _first_error(loop, task, want)
    result = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=f"rel1_v3_{task['id']}_{variant}_full_s0",
        measurement_gates=[
            GateResult("model_responses_structured", structured, layer="R0"),
            GateResult("fixed_five_call_budget", (loop["model_summary"] or {}).get("calls") == 5, layer="R0"),
            GateResult("model_did_not_issue_binding_ids", not loop["model_binding_attempt"], layer="R0"),
            GateResult("history_isolated_from_dispatcher", bool(loop["history_isolated"]), layer="R0"),
            GateResult("trust_updater_cannot_submit", bool(loop["updater_submit_denied"]), layer="R0"),
        ],
        artifact_gates=[
            GateResult("current_signals_delivered", bool(loop["current_delivery"].get("ok")), layer="R1"),
            GateResult("both_trust_messages_adopted", adopted, layer="R1"),
            GateResult("both_actions_bound", bool(loop["formation_action"] and loop["update_action"]), layer="R1"),
        ],
        criteria=[
            CriterionResult("observer_relay_faithful", "R2", "registered_signals", True, float(signals_ok), passed=signals_ok, critical=True),
            CriterionResult("formation_correct_counts", "R2", "frozen_oracle", True, float(counts_ok), passed=counts_ok, critical=True),
            CriterionResult("formation_support_rows", "R2", "frozen_oracle", True, float(support_ok), passed=support_ok, critical=True),
            CriterionResult("formation_source_selected", "R2", "frozen_oracle", True, float(formation_source_ok), passed=formation_source_ok, critical=True),
            CriterionResult("latest_binding_source_selected", "R2", "frozen_oracle", True, float(update_source_ok), passed=update_source_ok, critical=True),
            CriterionResult("latest_binding_evidence_latest_only", "R2", "row_ids", True, float(update_evidence_ok), passed=update_evidence_ok, critical=True),
            CriterionResult("formation_action_platform_bound", "R2", "trust_ledger", True, float(formation_action_ok), passed=formation_action_ok, critical=True),
            CriterionResult("update_action_platform_bound", "R2", "trust_ledger", True, float(update_action_ok), passed=update_action_ok, critical=True),
        ],
        process_profile={"first_error": error, "events": loop["events"], "relationships": loop["relationships"]},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "track": "full",
            "seed": 0,
            "first_error": error,
            "observer_relay_faithful": signals_ok,
            "formation_counts_correct": counts_ok,
            "formation_source_correct": formation_source_ok,
            "update_source_correct": update_source_ok,
            "formation_action_bound": formation_action_ok,
            "update_action_bound": update_action_ok,
            "got_formation": formation,
            "got_update": update,
            "got_formation_action": loop["formation_action"],
            "got_update_action": loop["update_action"],
            "want": want,
            "model_evidence_ids": loop["model_evidence_ids"],
        },
    )
    result["ranking_eligible"] = False
    return result
