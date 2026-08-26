"""Evidence-only scorer for the T4-v2 model pilot."""

from __future__ import annotations

from typing import Any

from benchmark_core.result import RunContext, compose_cell
from model_pilot.evidence import model_trace_evidence, read_jsonl
from v0_first_batch.schema import CriterionResult, GateResult

WORKFLOW_ID = "model_pilot_t4_v2"
SCORER_VERSION = "model-pilot-t4-v2-scorer-v1"


def score_cell(
    *,
    task: dict[str, Any],
    variant: str,
    track: str,
    seed: int,
    loop: dict[str, Any],
    eval_mode_evidence: dict[str, Any],
) -> dict[str, Any]:
    network_rows = read_jsonl(str(loop.get("trace_path") or ""))
    model = model_trace_evidence(str(loop.get("model_trace_path") or ""))
    event_names = [str(row.get("event") or "") for row in network_rows]
    target = str(task["target"])
    target_received = any(
        row.get("event") == "message_delivered"
        and str(row.get("receiver_id")) == target
        for row in network_rows
    )
    target_accepted = any(
        row.get("event") == "message_accepted"
        and str(row.get("node_id")) == target
        for row in network_rows
    )
    path = [str(task["source"])]
    for row in network_rows:
        if row.get("event") == "message_delivered":
            path.append(str(row.get("receiver_id") or ""))
    full_path = path == [str(node) for node in task["path"]]
    action_rows = [
        row for row in network_rows if row.get("event") == "action_submitted"
    ]
    action = dict(action_rows[-1].get("action") or {}) if action_rows else {}
    expected_action = str(task[f"{variant}_payload"]["target_action"])
    action_correct = action.get("action") == expected_action
    bridge_effective = (
        track == "full"
        or (
            track == "remove_bridge"
            and "edge_removed" in event_names
            and not target_received
        )
        or (
            track == "drop_bridge"
            and "message_dropped" in event_names
            and not target_received
        )
    )
    allowed_denials = {
        "edge_unavailable",
        "action_evidence_missing",
        "action_evidence_not_adopted",
    }
    denials = {
        str(row.get("reason") or "")
        for row in network_rows
        if row.get("event") == "denied"
    }
    execution_valid = bool(network_rows) and denials <= allowed_denials
    first_error = "none"
    if not model["contract_ok"]:
        first_error = "model_response_contract_invalid"
    elif track == "full" and not target_received:
        first_error = "registered_update_not_delivered"
    elif track == "full" and not target_accepted:
        first_error = "registered_update_not_accepted"
    elif (
        variant == "intervention"
        and track in {"remove_bridge", "drop_bridge"}
        and not target_received
    ):
        first_error = "bridge_message_not_delivered"
    elif not action_correct:
        first_error = "target_action_incorrect"

    run_id = f"model_v2_{task['id']}_{variant}_{track}_s{seed}"
    evidence_ids = [str(loop["trace_path"]), str(loop["model_trace_path"])]
    evidence_ids.extend(model["evidence_ids"])
    if action.get("action_id"):
        evidence_ids.append(str(action["action_id"]))
    context = RunContext(
        run_id=run_id,
        task_id=str(task["id"]),
        task_family="T4",
        mechanism_condition=f"M3-M5-M8:{track}:registered_transport_v2",
        variant=variant,
        seed=seed,
        track=track,
        model_version=str(model["model_version"]),
        temperature=float(model["temperature"]),
        budget={"model_calls": int(model["calls"])},
        environment_version="gaworld-network-channel-v1",
        trace_version="network-and-model-jsonl-v1",
        scorer_version=SCORER_VERSION,
        evidence_id=f"bundle:{run_id}",
    )
    cell = compose_cell(
        workflow_id=WORKFLOW_ID,
        context=context,
        eval_mode_evidence=eval_mode_evidence,
        measurement_gates=[
            GateResult("network_trace_parseable", bool(network_rows), layer="R0"),
            GateResult("model_trace_parseable", model["trace_parseable"], layer="R0"),
            GateResult("execution_valid", execution_valid, layer="R0"),
            GateResult("bridge_intervention_effective", bridge_effective, layer="R0"),
        ],
        artifact_gates=[
            GateResult(
                "model_responses_structured",
                model["contract_ok"],
                layer="R1",
                detail=",".join(model["errors"]),
            ),
            GateResult("target_action_present", bool(action), layer="R1"),
        ],
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
            "events": event_names,
            "path_to_target": path,
            "target_received": target_received,
            "target_accepted": target_accepted,
            "model_errors": model["errors"],
        },
        extra={
            "phase": "model_seed0_offline_calibration",
            "provider": model["provider"],
            "model_calls": model["calls"],
            "expected_action": expected_action,
            "action": action,
            "base_release": "benchmark-v1.1-rule",
            "message_class": task["message_class"],
            "transport_rule": "always_forward_registered_update",
        },
    )
    cell["ranking_eligible"] = False
    return cell
