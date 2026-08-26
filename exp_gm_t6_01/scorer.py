"""Independent distribution scorer for T6 population approximation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark_core.result import RunContext, compose_cell
from exp_gm_t6_01.loader import members_for
from v0_first_batch.schema import CriterionResult, GateResult

WORKFLOW_ID = "exp_gm_t6_01_population"
SCORER_VERSION = "t6-01-scorer-v1"
TOLERANCE = 1e-9


def _trace_rows(path: str) -> list[dict[str, Any]]:
    trace = Path(path)
    if not trace.is_file() or trace.stat().st_size == 0:
        return []
    return [
        json.loads(line)
        for line in trace.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _moments(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return mean, variance


def _oracle(task: dict[str, Any]) -> dict[str, Any]:
    states = {
        str(member["agent_id"]): {
            "subgroup": str(member["subgroup"]),
            "value": float(member["value"]),
        }
        for member in members_for(task)
    }
    persistence = float(task["persistence"])
    drift = {
        str(group): float(value) for group, value in task["subgroup_drift"].items()
    }
    shocks = {int(day): float(value) for day, value in task["shocks"].items()}
    for day in range(1, int(task["days"]) + 1):
        for state in states.values():
            state["value"] = (
                persistence * float(state["value"])
                + drift[str(state["subgroup"])]
                + shocks.get(day, 0.0)
            )
    subgroup_values: dict[str, list[float]] = {}
    for state in states.values():
        subgroup_values.setdefault(str(state["subgroup"]), []).append(
            float(state["value"])
        )
    subgroups: dict[str, dict[str, float | int]] = {}
    all_values: list[float] = []
    for subgroup, values in subgroup_values.items():
        mean, variance = _moments(values)
        subgroups[subgroup] = {
            "count": len(values),
            "mean": mean,
            "variance": variance,
        }
        all_values.extend(values)
    overall_mean, overall_variance = _moments(all_values)
    return {
        "population_count": len(all_values),
        "overall_mean": overall_mean,
        "overall_variance": overall_variance,
        "subgroups": subgroups,
    }


def _distribution_errors(
    actual: dict[str, Any], expected: dict[str, Any]
) -> dict[str, float]:
    errors = {
        "overall_mean": abs(
            float(actual.get("overall_mean") or 0.0) - float(expected["overall_mean"])
        ),
        "overall_variance": abs(
            float(actual.get("overall_variance") or 0.0)
            - float(expected["overall_variance"])
        ),
        "subgroup_mean": 0.0,
        "subgroup_variance": 0.0,
    }
    actual_groups = dict(actual.get("subgroups") or {})
    for subgroup, expected_group in expected["subgroups"].items():
        actual_group = dict(actual_groups.get(subgroup) or {})
        errors["subgroup_mean"] = max(
            errors["subgroup_mean"],
            abs(float(actual_group.get("mean") or 0.0) - float(expected_group["mean"])),
        )
        errors["subgroup_variance"] = max(
            errors["subgroup_variance"],
            abs(
                float(actual_group.get("variance") or 0.0)
                - float(expected_group["variance"])
            ),
        )
    return errors


def score_cell(
    *,
    task: dict[str, Any],
    mode: str,
    track: str,
    seed: int,
    loop: dict[str, Any],
    eval_mode_evidence: dict[str, Any],
) -> dict[str, Any]:
    trace_rows = _trace_rows(str(loop.get("trace_path") or ""))
    event_names = [str(row.get("event") or "") for row in trace_rows]
    completion_rows = [
        row for row in trace_rows if row.get("event") == "projection_completed"
    ]
    summary = dict(completion_rows[-1].get("summary") or {}) if completion_rows else {}
    expected = _oracle(task)
    errors = _distribution_errors(summary, expected)
    max_error = max(errors.values())
    distribution_ok = (
        max_error <= TOLERANCE
        and int(summary.get("population_count") or 0) == expected["population_count"]
    )
    completed = (
        bool(completion_rows and completion_rows[-1].get("completed"))
        and int(summary.get("day") or -1) == int(task["days"])
        and "projection_completed" in event_names
    )
    checkpoint_ok = track == "continuous" or (
        bool(loop.get("checkpoint_nonempty"))
        and "checkpoint_written" in event_names
        and "checkpoint_loaded" in event_names
    )
    member_count = len(members_for(task))
    group_count = len(task["subgroup_values"])
    days = int(task["days"])
    operations = int(summary.get("operation_units") or 0)
    if mode == "individual":
        cost_ok = operations == member_count * days
    elif mode == "cohort":
        cost_ok = operations == group_count * days
    else:
        cost_ok = 0 < operations < group_count * days
    first_error = "none"
    if not completed:
        first_error = "longitudinal_projection_incomplete"
    elif not checkpoint_ok:
        first_error = "checkpoint_resume_invalid"
    elif not distribution_ok:
        first_error = "registered_distribution_not_preserved"
    elif not cost_ok:
        first_error = "operation_cost_contract_failed"
    run_id = f"{task['id']}_{mode}_{track}_s{seed}"
    evidence_ids = [str(loop["trace_path"])]
    if loop.get("checkpoint_path"):
        evidence_ids.append(str(loop["checkpoint_path"]))
    context = RunContext(
        run_id=run_id,
        task_id=str(task["id"]),
        task_family="T6",
        mechanism_condition=f"M2-M7-M9:{mode}:{track}",
        variant=mode,
        seed=seed,
        track=track,
        model_version="rule",
        temperature=0,
        budget={"logical_calls": 0, "operation_units": operations},
        environment_version="gaworld-population-projection-v1",
        trace_version="population-projection-jsonl-v1",
        scorer_version=SCORER_VERSION,
        evidence_id=f"bundle:{run_id}",
    )
    cell = compose_cell(
        workflow_id=WORKFLOW_ID,
        context=context,
        eval_mode_evidence=eval_mode_evidence,
        measurement_gates=[
            GateResult("trace_parseable", bool(trace_rows), layer="R0"),
            GateResult("projection_completed", completed, layer="R0"),
            GateResult("checkpoint_integrity", checkpoint_ok, layer="R0"),
        ],
        artifact_gates=[
            GateResult("final_population_summary_present", bool(summary), layer="R1")
        ],
        criteria=[
            CriterionResult(
                "registered_distribution_preserved",
                "R2",
                "independent_individual_oracle",
                True,
                1.0 if distribution_ok else 0.0,
                passed=distribution_ok,
                critical=True,
                evidence_ids=evidence_ids,
                detail=f"errors={errors}",
            ),
            CriterionResult(
                "operation_cost_contract",
                "R3",
                "registered_operation_units",
                True,
                1.0 if cost_ok else 0.0,
                passed=cost_ok,
                evidence_ids=[str(loop["trace_path"])],
                detail=f"mode={mode},operations={operations}",
            ),
        ],
        process_profile={
            "first_error": first_error,
            "events": event_names,
            "distribution_errors": errors,
        },
        extra={
            "mode": mode,
            "max_distribution_error": max_error,
            "operation_units": operations,
            "population_count": member_count,
            "subgroup_count": group_count,
            "registered_scope": [
                "mean",
                "variance",
                "subgroup_mean",
                "subgroup_variance",
            ],
            "excluded_scope": [
                "individual_trajectory",
                "quantiles",
                "network_structure",
            ],
            "rule_calibration": True,
        },
    )
    cell["ranking_eligible"] = False
    return cell
