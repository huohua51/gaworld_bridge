"""Evidence-only scorer for T5-v3 resident eligibility-scope repeats."""

from __future__ import annotations

import json
from typing import Any

from benchmark_core.result import RunContext, compose_cell
from exp_gm_t5_03.semantics import expected_actions
from model_pilot.evidence import model_trace_evidence, read_jsonl
from v0_first_batch.schema import CriterionResult, GateResult

WORKFLOW_ID = "model_pilot_t5_v3_scope"
SCORER_VERSION = "model-pilot-t5-v3-scope-scorer-v1"


def _contains_key(value: Any, forbidden: str) -> bool:
    if isinstance(value, dict):
        return forbidden in value or any(
            _contains_key(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, forbidden) for item in value)
    return False


def _decisions(model: dict[str, Any]) -> list[dict[str, Any]]:
    responses = {
        str(row.get("call_id") or ""): row for row in model.get("responses") or []
    }
    decisions: list[dict[str, Any]] = []
    for request in model.get("requests") or []:
        call_id = str(request.get("call_id") or "")
        response = responses.get(call_id) or {}
        prompt = json.loads(str(request.get("prompt") or "{}"))
        context = prompt.get("policy_context") or {}
        directive = prompt.get("resident_directive") or {}
        parsed = response.get("parsed") or {}
        expected = {
            "notice_seen": context.get("notice_present"),
            "binding": context.get("binding"),
            "target_match": directive.get("target_match"),
            "authorized": directive.get("authorized"),
            "action": directive.get("action"),
        }
        semantic_correct = response.get("ok") is True and all(
            parsed.get(field) is expected[field]
            for field in ("notice_seen", "binding", "target_match", "authorized")
        )
        action_correct = bool(
            response.get("ok") is True and parsed.get("action") == expected["action"]
        )
        prompt_unambiguous = bool(
            not _contains_key(prompt, "required_action")
            and directive.get("authority") == "sole_action_authority"
            and directive.get("action") in prompt.get("candidate_actions", [])
        )
        decisions.append(
            {
                "agent_id": str(request.get("agent_id") or ""),
                "policy_state": str(context.get("status") or ""),
                "expected": expected,
                "actual": {
                    field: parsed.get(field)
                    for field in (
                        "notice_seen",
                        "binding",
                        "target_match",
                        "authorized",
                        "action",
                    )
                },
                "semantic_correct": semantic_correct,
                "action_correct": action_correct,
                "prompt_unambiguous": prompt_unambiguous,
                "prompt_sha256": str(request.get("prompt_sha256") or ""),
                "evidence_id": str(response.get("evidence_id") or ""),
            }
        )
    return decisions


def score_cell(
    *,
    task: dict[str, Any],
    policy_state: str,
    track: str,
    repeat_id: int,
    loop: dict[str, Any],
    eval_mode_evidence: dict[str, Any],
) -> dict[str, Any]:
    policy_rows = read_jsonl(str(loop.get("trace_path") or ""))
    model = model_trace_evidence(str(loop.get("model_trace_path") or ""))
    decisions = _decisions(model)
    resident_count = len(task["residents"])
    prompt_unambiguous = len(decisions) == resident_count and all(
        item["prompt_unambiguous"] for item in decisions
    )
    semantics_correct = len(decisions) == resident_count and all(
        item["semantic_correct"] for item in decisions
    )
    directive_actions_correct = len(decisions) == resident_count and all(
        item["action_correct"] for item in decisions
    )

    event_names = [str(row.get("event") or "") for row in policy_rows]
    action_rows = [
        row for row in policy_rows if row.get("event") == "resident_action_submitted"
    ]
    actual = {
        str(row.get("agent_id") or ""): str(
            (row.get("action_record") or {}).get("action") or ""
        )
        for row in action_rows
    }
    expected = expected_actions(task, policy_state)
    response_correct = actual == expected
    changed = {
        str(row.get("agent_id") or "")
        for row in action_rows
        if dict(row.get("state_after") or {}) != dict(row.get("state_before") or {})
    }
    target_groups = {str(group) for group in task["target_groups"]}
    target_agents = {
        str(resident["agent_id"])
        for resident in task["residents"]
        if str(resident["group"]) in target_groups
    }
    expected_changed = target_agents if policy_state == "binding" else set()
    effect_correct = changed == expected_changed
    policy_expected = policy_state != "absence"
    registered = "policy_registered" in event_names
    activated = "policy_activated" in event_names
    perception_count = sum(1 for name in event_names if name == "policy_perceived")
    delivery_complete = not policy_expected or perception_count == resident_count
    mechanism_active = not policy_expected or (
        track == "full" and registered and activated and delivery_complete
    )
    allowed_denials = {
        "policy_not_active",
        "action_evidence_not_perceived",
        "action_evidence_missing",
        "action_not_registered",
    }
    denials = {
        str(row.get("reason") or "")
        for row in policy_rows
        if row.get("event") == "denied"
    }
    execution_valid = bool(policy_rows) and denials <= allowed_denials
    all_actions_present = set(actual) == set(expected) and all(actual.values())

    first_error = "none"
    if not prompt_unambiguous:
        first_error = "eligibility_scope_prompt_ambiguous"
    elif not model["contract_ok"]:
        first_error = "model_response_contract_invalid"
    elif not semantics_correct:
        first_error = "resident_scope_semantics_incorrect"
    elif not directive_actions_correct:
        first_error = "resident_directive_not_followed"
    elif not response_correct:
        first_error = "resident_policy_response_incorrect"
    elif not effect_correct:
        first_error = "policy_effect_or_spillover_incorrect"

    run_id = f"model_v3_{task['id']}_{policy_state}_{track}_r{repeat_id}"
    evidence_ids = [str(loop["trace_path"]), str(loop["model_trace_path"])]
    evidence_ids.extend(model["evidence_ids"])
    evidence_ids.extend(
        str((row.get("action_record") or {}).get("action_id"))
        for row in action_rows
        if (row.get("action_record") or {}).get("action_id")
    )
    decision_evidence = [
        str(item["evidence_id"]) for item in decisions if item["evidence_id"]
    ]
    context = RunContext(
        run_id=run_id,
        task_id=str(task["id"]),
        task_family="T5",
        mechanism_condition=f"M1-M4-M8:{policy_state}:{track}:scope_v3",
        variant=policy_state,
        seed=repeat_id,
        track=track,
        model_version=str(model["model_version"]),
        temperature=float(model["temperature"]),
        budget={"model_calls": int(model["calls"])},
        environment_version="gaworld-urban-policy-v1",
        trace_version="urban-policy-and-model-jsonl-v3",
        scorer_version=SCORER_VERSION,
        evidence_id=f"bundle:{run_id}",
    )
    cell = compose_cell(
        workflow_id=WORKFLOW_ID,
        context=context,
        eval_mode_evidence=eval_mode_evidence,
        measurement_gates=[
            GateResult("policy_trace_parseable", bool(policy_rows), layer="R0"),
            GateResult("model_trace_parseable", model["trace_parseable"], layer="R0"),
            GateResult("execution_valid", execution_valid, layer="R0"),
            GateResult(
                "policy_mechanism_activated",
                mechanism_active,
                layer="R0",
                detail=(
                    f"registered={registered},activated={activated},"
                    f"perceptions={perception_count}"
                ),
            ),
        ],
        artifact_gates=[
            GateResult(
                "scope_prompt_unambiguous",
                prompt_unambiguous,
                layer="R1",
                detail="no required_action key; one sole resident directive",
            ),
            GateResult(
                "model_responses_structured",
                model["contract_ok"],
                layer="R1",
                detail=",".join(model["errors"]),
            ),
            GateResult("resident_actions_complete", all_actions_present, layer="R1"),
        ],
        criteria=[
            CriterionResult(
                "resident_scope_semantics_correct",
                "R2",
                "registered_scope_directive_v3",
                True,
                1.0 if semantics_correct else 0.0,
                passed=semantics_correct,
                critical=True,
                evidence_ids=decision_evidence,
                detail=json.dumps(decisions, ensure_ascii=False, sort_keys=True),
            ),
            CriterionResult(
                "resident_directive_followed",
                "R2",
                "sole_action_authority_v3",
                True,
                1.0 if directive_actions_correct else 0.0,
                passed=directive_actions_correct,
                critical=True,
                evidence_ids=decision_evidence,
            ),
            CriterionResult(
                "policy_response_correct",
                "R2",
                "registered_population_oracle_v3",
                True,
                1.0 if response_correct and effect_correct else 0.0,
                passed=response_correct and effect_correct,
                critical=True,
                evidence_ids=evidence_ids,
                detail=f"expected={expected} actual={actual}",
            ),
            CriterionResult(
                "no_untargeted_spillover",
                "R3",
                "state_delta",
                True,
                1.0 if changed <= target_agents else 0.0,
                passed=changed <= target_agents,
                evidence_ids=[str(loop["trace_path"])],
            ),
        ],
        process_profile={
            "first_error": first_error,
            "events": event_names,
            "scope_decisions": decisions,
            "expected_actions": expected,
            "actual_actions": actual,
            "model_errors": model["errors"],
        },
        extra={
            "phase": "eligibility_scope_repeat",
            "provider": model["provider"],
            "model_calls": model["calls"],
            "policy_state": policy_state,
            "repeat_id": repeat_id,
            "behavior_change_rate": len(changed) / resident_count,
            "changed_agent_ids": sorted(changed),
            "target_agent_ids": sorted(target_agents),
            "prompt_sha256_by_resident": {
                item["agent_id"]: item["prompt_sha256"] for item in decisions
            },
            "base_release": "benchmark-v1.1-rule",
        },
    )
    cell["ranking_eligible"] = False
    return cell


__all__ = ["SCORER_VERSION", "WORKFLOW_ID", "score_cell"]
