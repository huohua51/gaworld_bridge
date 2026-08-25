"""Score EXP-GM-OA-01 cells. Do not use aggregate EventValue as the conclusion."""

from __future__ import annotations

from typing import Any

from exp_gm_oa_01.channel import NONE
from exp_gm_oa_01.loader import oracle_of
from exp_gm_oa_01.prompts import _as_bool
from v0_first_batch.schema import CriterionResult, GateResult, compose

FIRST_ERRORS = (
    "fields_not_extractable",
    "need_change_action_inconsistent",
    "keep_placeholder_not_none",
    "control_false_positive_change",
    "intervention_missed_change",
    "wrong_target",
    "wrong_value",
    "wrong_evidence",
    "environment_rewrote_plan",
    "none",
)


def normalize_value(value: Any) -> Any:
    if value is None:
        return NONE
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.upper() == NONE:
        return NONE
    try:
        if text.startswith("-"):
            return int(text)
        if text.isdigit():
            return int(text)
    except ValueError:
        pass
    return text


def values_equal(left: Any, right: Any) -> bool:
    return normalize_value(left) == normalize_value(right)


def changed_fields(action: dict[str, Any]) -> bool:
    if action.get("action") == "revise":
        return True
    return normalize_value(action.get("target")) != NONE or normalize_value(action.get("value")) != NONE


def need_change_consistent(protocol: str, action: dict[str, Any]) -> bool:
    if protocol != "need_change_gate":
        return True
    flag = _as_bool(action.get("need_change"))
    if flag is None:
        return False
    if flag:
        return action.get("action") == "revise"
    return action.get("action") == "keep"


def predicted_need_change(protocol: str, action: dict[str, Any]) -> bool | None:
    if protocol == "need_change_gate":
        return _as_bool(action.get("need_change"))
    if action.get("action") == "revise":
        return True
    if action.get("action") == "keep":
        return False
    return None


def action_matches_oracle(task: dict[str, Any], variant: str, protocol: str, action: dict[str, Any], notice: dict[str, Any]) -> bool:
    oracle = oracle_of(task, variant)
    event_id = str((notice or {}).get("event_id") or "")
    if not need_change_consistent(protocol, action):
        return False
    if protocol == "need_change_gate" and bool(action.get("need_change")) != bool(oracle["need_change"]):
        return False
    if action.get("action") != oracle["action"]:
        return False
    if not values_equal(action.get("target"), oracle["target"]):
        return False
    if not values_equal(action.get("value"), oracle["value"]):
        return False
    return str(action.get("evidence_event_id") or "") == event_id


def first_error(
    *,
    variant: str,
    protocol: str,
    loop: dict[str, Any],
    action: dict[str, Any],
    task: dict[str, Any],
) -> str:
    if loop.get("contract_error") in {"fields_not_extractable", "empty"}:
        return "fields_not_extractable"
    if loop.get("env_rewrote") or loop.get("source_contamination"):
        return "environment_rewrote_plan"
    if not need_change_consistent(protocol, action):
        return "need_change_action_inconsistent"
    oracle = oracle_of(task, variant)
    notice = loop.get("notice") or {}
    event_id = str(notice.get("event_id") or "")
    if variant == "control":
        if action.get("action") == "revise":
            return "control_false_positive_change"
        if action.get("action") != "keep" or changed_fields(action):
            return "keep_placeholder_not_none"
        if str(action.get("evidence_event_id") or "") != event_id:
            return "wrong_evidence"
        return "none"
    if action.get("action") == "keep" or not changed_fields(action):
        return "intervention_missed_change"
    if not values_equal(action.get("target"), oracle["target"]):
        return "wrong_target"
    if not values_equal(action.get("value"), oracle["value"]):
        return "wrong_value"
    if str(action.get("evidence_event_id") or "") != event_id:
        return "wrong_evidence"
    return "none"


def score_cell(
    *,
    task: dict[str, Any],
    variant: str,
    protocol: str,
    seed: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    action = loop.get("action") or {}
    notice = loop.get("notice") or {}
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    actual_need = variant == "intervention"
    predicted = predicted_need_change(protocol, action) if extractable else None
    consistent = need_change_consistent(protocol, action) if extractable else False
    need_change_correct = bool(
        extractable and predicted is not None and predicted == actual_need and consistent
    )
    target_correct = bool(
        extractable
        and not loop.get("env_rewrote")
        and action_matches_oracle(task, variant, protocol, action, notice)
    )
    err = first_error(variant=variant, protocol=protocol, loop=loop, action=action, task=task)
    cell = compose(
        workflow_id=workflow_id,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("event_injected", "event_injected" in (loop.get("events") or []) and bool(loop.get("injected")), layer="R0"),
            GateResult("current_state_seeded", "current_state_seeded" in (loop.get("events") or []), layer="R0"),
            GateResult("fields_extractable", extractable, layer="R0"),
            GateResult("single_call", int(loop.get("agent_calls") or 0) == 1, layer="R0"),
            GateResult("eval_mode_on", True, layer="R0"),
        ],
        artifact_gates=[
            GateResult("action_submitted_by_agent", "action_submitted" in (loop.get("events") or []), layer="R1"),
            GateResult(
                "environment_did_not_rewrite",
                not loop.get("env_rewrote"),
                layer="R1",
                detail="source_contamination" if loop.get("env_rewrote") else "",
            ),
        ],
        criteria=[
            CriterionResult(
                criterion_id="need_change_correct",
                layer="R2",
                scorer="oa_need_change",
                evaluable=extractable,
                score=1.0 if need_change_correct else 0.0,
                passed=need_change_correct,
                critical=False,
                detail=f"predicted={predicted} actual={actual_need} consistent={consistent}",
            ),
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="oa_oracle",
                evaluable=extractable,
                score=1.0 if target_correct else 0.0,
                passed=target_correct,
                critical=True,
                detail=f"action={action.get('action')} target={action.get('target')} value={action.get('value')}",
            ),
        ],
        process_profile={
            "first_error": err,
            "events": loop.get("events"),
            "agent_calls": loop.get("agent_calls"),
            "protocol": protocol,
            "variant": variant,
            "injected_event_id": (loop.get("injected") or {}).get("event_id"),
            "source_contamination": bool(loop.get("source_contamination")),
        },
        extra={
            "task_id": task["id"],
            "protocol": protocol,
            "variant": variant,
            "seed": seed,
            "need_change_correct": need_change_correct,
            "target_correct": target_correct,
            "predicted_need_change": predicted,
            "actual_need_change": actual_need,
            "unnecessary_replan": variant == "control" and changed_fields(action),
            "action": action,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell


def _protocol_cells(cells: list[dict], protocol: str, variant: str | None = None) -> list[dict]:
    subset = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if extra.get("protocol") != protocol:
            continue
        if variant is not None and extra.get("variant") != variant:
            continue
        if not cell.get("measurement_valid"):
            continue
        subset.append(cell)
    return subset


def _mean_flag(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in cells) / len(cells), 4)


def coverage(cells: list[dict], protocol: str | None = None) -> float:
    subset = cells if protocol is None else [c for c in cells if (c.get("extra") or {}).get("protocol") == protocol]
    if not subset:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in subset) / len(subset), 4)


def need_change_accuracy(cells: list[dict], protocol: str) -> float | None:
    return _mean_flag(_protocol_cells(cells, protocol), "need_change_correct")


def control_stability_rate(cells: list[dict], protocol: str) -> float | None:
    return _mean_flag(_protocol_cells(cells, protocol, "control"), "target_correct")


def adaptation_rate(cells: list[dict], protocol: str) -> float | None:
    return _mean_flag(_protocol_cells(cells, protocol, "intervention"), "target_correct")


def unnecessary_replan_rate(cells: list[dict], protocol: str) -> float | None:
    return _mean_flag(_protocol_cells(cells, protocol, "control"), "unnecessary_replan")


def conditional_action_score(cells: list[dict], protocol: str) -> float | None:
    stability = control_stability_rate(cells, protocol)
    adapt = adaptation_rate(cells, protocol)
    if stability is None or adapt is None:
        return None
    return round((stability + adapt) / 2, 4)
