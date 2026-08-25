"""OA-02 scorer. Do not import or modify exp_gm_oa_01.scorer."""

from __future__ import annotations

from typing import Any

from exp_gm_oa_01.loader import oracle_of
from exp_gm_oa_02.contract import (
    CONTRACT_ACTION,
    CONTRACT_KEEP_EXTRA,
    CONTRACT_REVISE_MISSING,
    KEEP,
    REVISE,
    is_contract_failure,
)
from v0_first_batch.schema import CriterionResult, GateResult, compose


def normalize_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = str(value).strip()
    try:
        if text.startswith("-") or text.isdigit():
            return int(text)
    except ValueError:
        pass
    return text


def values_equal(left: Any, right: Any) -> bool:
    return normalize_value(left) == normalize_value(right)


def expected_action(variant: str) -> str:
    return KEEP if variant == "control" else REVISE


def action_selection_correct(variant: str, action: dict[str, Any]) -> bool:
    return action.get("action") == expected_action(variant)


def target_correct(task: dict[str, Any], variant: str, action: dict[str, Any], *, contract_ok: bool) -> bool:
    if not contract_ok:
        return False
    if variant == "control":
        return action.get("action") == KEEP
    oracle = oracle_of(task, variant)
    return (
        action.get("action") == REVISE
        and values_equal(action.get("target"), oracle["target"])
        and values_equal(action.get("value"), oracle["value"])
    )


def oracle_full(task: dict[str, Any], variant: str, loop: dict[str, Any]) -> bool:
    action = loop.get("action") or {}
    notice = loop.get("notice") or {}
    if loop.get("contract_error") != "ok" or loop.get("env_rewrote"):
        return False
    event_id = str(notice.get("event_id") or "")
    if str(action.get("evidence_event_id") or "") != event_id:
        return False
    return target_correct(task, variant, action, contract_ok=True)


def first_error(*, variant: str, loop: dict[str, Any], task: dict[str, Any]) -> str:
    reason = str(loop.get("contract_error") or "empty")
    action = loop.get("action") or {}
    if reason in {"fields_not_extractable", "empty"}:
        return "fields_not_extractable"
    if loop.get("env_rewrote") or loop.get("source_contamination"):
        return "environment_rewrote_plan"
    if reason == CONTRACT_KEEP_EXTRA:
        return CONTRACT_KEEP_EXTRA
    if reason == CONTRACT_REVISE_MISSING:
        return CONTRACT_REVISE_MISSING
    if reason == CONTRACT_ACTION:
        return CONTRACT_ACTION
    notice = loop.get("notice") or {}
    event_id = str(notice.get("event_id") or "")
    if variant == "control":
        if action.get("action") == REVISE:
            return "control_false_positive_change"
        if action.get("action") != KEEP:
            return CONTRACT_ACTION
        if str(action.get("evidence_event_id") or "") != event_id:
            return "wrong_evidence"
        return "none"
    oracle = oracle_of(task, variant)
    if action.get("action") == KEEP:
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
    seed: int,
    loop: dict[str, Any],
    workflow_id: str,
    instance_id: str,
) -> dict[str, Any]:
    action = loop.get("action") or {}
    extractable = loop.get("contract_error") not in {"fields_not_extractable", "empty"}
    contract_ok = loop.get("contract_error") == "ok"
    selected = action_selection_correct(variant, action) if extractable else False
    target_ok = target_correct(task, variant, action, contract_ok=contract_ok) if extractable else False
    full = oracle_full(task, variant, loop) if extractable else False
    err = first_error(variant=variant, loop=loop, task=task)
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
            GateResult("environment_did_not_rewrite", not loop.get("env_rewrote"), layer="R1"),
            GateResult(
                "contract_accepted",
                contract_ok,
                layer="R1",
                detail=str(loop.get("contract_error") or ""),
            ),
        ],
        criteria=[
            CriterionResult(
                criterion_id="action_selection_correct",
                layer="R2",
                scorer="oa02_action",
                evaluable=extractable,
                score=1.0 if selected else 0.0,
                passed=selected,
                critical=False,
                detail=f"action={action.get('action')} expected={expected_action(variant)}",
            ),
            CriterionResult(
                criterion_id="target_correct",
                layer="R2",
                scorer="oa02_target",
                evaluable=extractable,
                score=1.0 if target_ok else 0.0,
                passed=target_ok,
                critical=False,
                detail=f"target={action.get('target')} value={action.get('value')}",
            ),
            CriterionResult(
                criterion_id="oracle_conditioned_success",
                layer="R3",
                scorer="oa02_oracle",
                evaluable=extractable,
                score=1.0 if full else 0.0,
                passed=full,
                critical=True,
                detail=f"evidence={action.get('evidence_event_id')}",
            ),
        ],
        process_profile={
            "first_error": err,
            "events": loop.get("events"),
            "agent_calls": loop.get("agent_calls"),
            "contract_error": loop.get("contract_error"),
            "injected_event_id": (loop.get("injected") or {}).get("event_id"),
            "source_contamination": bool(loop.get("source_contamination")),
        },
        extra={
            "task_id": task["id"],
            "protocol": "exclusive_keep_revise",
            "variant": variant,
            "seed": seed,
            "action_selection_correct": selected,
            "target_correct": target_ok,
            "oracle_conditioned_success": full,
            "contract_rejected": bool(loop.get("contract_rejected")),
            "action": action,
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    return cell


def _valid(cells: list[dict], variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if extra.get("protocol") and extra.get("protocol") != "exclusive_keep_revise":
            continue
        if variant is not None and extra.get("variant") != variant:
            continue
        if cell.get("measurement_valid"):
            out.append(cell)
    return out


def _mean_flag(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in cells) / len(cells), 4)


def coverage(cells: list[dict]) -> float:
    if not cells:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in cells) / len(cells), 4)


def action_selection_accuracy(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells), "action_selection_correct")


def control_stability_rate(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells, "control"), "oracle_conditioned_success")


def adaptation_rate(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells, "intervention"), "oracle_conditioned_success")


def contract_failure_rate(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells), "contract_rejected")


def target_correct_rate(cells: list[dict]) -> float | None:
    return _mean_flag(_valid(cells), "target_correct")


def oracle_conditioned_full_pass(cells: list[dict]) -> float | None:
    scored = [c for c in _valid(cells) if c.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(c["full_pass"]) for c in scored) / len(scored), 4)
