"""Independent scorer for T4-v2 registered transport."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark_core.result import RunContext, compose_cell
from exp_gm_t4_02.loader import payload_for
from v0_first_batch.schema import CriterionResult, GateResult

WORKFLOW_ID = "exp_gm_t4_02_registered_transport"
SCORER_VERSION = "t4-02-scorer-v1"


def _trace_rows(path: str) -> list[dict[str, Any]]:
    trace = Path(path)
    if not trace.is_file() or trace.stat().st_size == 0:
        return []
    return [
        json.loads(line)
        for line in trace.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _first_error(
    *,
    variant: str,
    track: str,
    target_received: bool,
    target_accepted: bool,
    action_correct: bool,
) -> str:
    if track == "full" and not target_received:
        return "registered_update_not_delivered"
    if track == "full" and not target_accepted:
        return "registered_update_not_accepted"
    if (
        variant == "intervention"
        and track in {"remove_bridge", "drop_bridge"}
        and not target_received
    ):
        return "bridge_message_not_delivered"
    if not action_correct:
        return "target_action_incorrect"
    return "none"


def score_cell(
    *,
    task: dict[str, Any],
    variant: str,
    track: str,
    seed: int,
    loop: dict[str, Any],
    eval_mode_evidence: dict[str, Any],
) -> dict[str, Any]:
    trace_rows = _trace_rows(str(loop.get("trace_path") or ""))
    events = [str(row.get("event") or "") for row in trace_rows]
    action = dict(loop.get("action") or {})
    expected_action = str(payload_for(task, variant)["target_action"])
    action_correct = action.get("action") == expected_action
    target_received = bool(loop.get("target_received"))
    target_accepted = bool(loop.get("target_accepted"))
    full_path = list(loop.get("path_to_target") or []) == list(task["path"])
    bridge_effective = (
        track == "full"
        or (
            track == "remove_bridge"
            and "edge_removed" in events
            and not target_received
        )
        or (
            track == "drop_bridge"
            and "message_dropped" in events
            and not target_received
        )
    )
    expected_denials = {"edge_unavailable"} if track == "remove_bridge" else set()
    denial_reasons = {
        str(item.get("reason") or "") for item in loop.get("denials") or []
    }
    execution_valid = (
        bool(trace_rows) and denial_reasons <= expected_denials and bridge_effective
    )
    first_error = _first_error(
        variant=variant,
        track=track,
        target_received=target_received,
        target_accepted=target_accepted,
        action_correct=action_correct,
    )
    evidence_ids = [str(loop["trace_path"])]
    if action.get("action_id"):
        evidence_ids.append(str(action["action_id"]))
    run_id = f"{task['id']}_{variant}_{track}_s{seed}"
    context = RunContext(
        run_id=run_id,
        task_id=str(task["id"]),
        task_family="T4",
        mechanism_condition=f"M3-M5-M8:{track}:registered_transport_v2",
        variant=variant,
        seed=seed,
        track=track,
        model_version="rule",
        temperature=0,
        budget={"logical_calls": 0, "channel_hops": len(task["path"]) - 1},
        environment_version="gaworld-network-channel-v1",
        trace_version="network-propagation-jsonl-v1",
        scorer_version=SCORER_VERSION,
        evidence_id=f"bundle:{run_id}",
    )
    cell = compose_cell(
        workflow_id=WORKFLOW_ID,
        context=context,
        eval_mode_evidence=eval_mode_evidence,
        measurement_gates=[
            GateResult("execution_valid", execution_valid, layer="R0"),
            GateResult("trace_parseable", bool(trace_rows), layer="R0"),
            GateResult("bridge_intervention_effective", bridge_effective, layer="R0"),
        ],
        artifact_gates=[GateResult("target_action_present", bool(action), layer="R1")],
        criteria=[
            CriterionResult(
                "target_action_correct",
                "R2",
                "registered_action_oracle",
                True,
                1.0 if action_correct else 0.0,
                passed=action_correct,
                critical=True,
                evidence_ids=evidence_ids,
                detail=f"got={action.get('action')} expected={expected_action}",
            ),
            CriterionResult(
                "target_update_accepted",
                "R3",
                "network_trace",
                True,
                1.0 if target_accepted else 0.0,
                passed=target_accepted,
                critical=track == "full",
                evidence_ids=[str(loop["trace_path"])],
            ),
            CriterionResult(
                "complete_propagation_path",
                "R3",
                "network_trace",
                True,
                1.0 if full_path else 0.0,
                passed=full_path,
                critical=track == "full",
                evidence_ids=[str(loop["trace_path"])],
            ),
        ],
        process_profile={
            "first_error": first_error,
            "events": events,
            "path_to_target": loop.get("path_to_target"),
            "target_received": target_received,
            "target_accepted": target_accepted,
        },
        extra={
            "expected_action": expected_action,
            "action": action,
            "bridge_active": loop.get("bridge_active"),
            "message_class": task["message_class"],
            "transport_rule": "always_forward_registered_update",
            "rule_calibration": True,
        },
    )
    cell["ranking_eligible"] = False
    return cell
