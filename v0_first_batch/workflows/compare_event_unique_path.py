"""W3: unique-intervention audit wrapped around compare-event.

Existing _compose_comparison_rows reports every metric delta. This workflow
registers one path and fails the audit if any other metric moved.
"""

from __future__ import annotations

import os
import tempfile

from v0_first_batch.paths import ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "compare_event_unique_path_001"
REGISTERED = {"mobility_intent"}
EPS = 1e-12


def _write_csv(path: str, rows: list[dict]) -> None:
    import pandas as pd

    pd.DataFrame(rows).to_csv(path, index=False)


def _series(metric: str, v0: float, v1: float) -> list[dict]:
    return [
        {"agent_id": 1, "step": 0, "metric": metric, "value": v0},
        {"agent_id": 1, "step": 1, "metric": metric, "value": v1},
    ]


def _audit(base_csv: str, event_csv: str) -> dict:
    ensure_import_paths()
    import generative_city_sim as sim

    rows = sim._compose_comparison_rows(base_csv, event_csv)
    leaked = []
    registered_deltas = {}
    for row in rows:
        metric = row["metric"]
        delta = float(row["delta_final"])
        if metric in REGISTERED:
            registered_deltas[metric] = delta
        elif abs(delta) > EPS:
            leaked.append({"metric": metric, "delta_final": delta})
    return {
        "rows": rows,
        "unique_path_ok": not leaked,
        "leaked_metrics": leaked,
        "registered_deltas": registered_deltas,
    }


def _score(instance_id: str, base_rows: list[dict], event_rows: list[dict], expect_change: bool) -> dict:
    tmp = tempfile.mkdtemp(prefix="gaw_pair_")
    base_csv = os.path.join(tmp, "base.csv")
    event_csv = os.path.join(tmp, "event.csv")
    _write_csv(base_csv, base_rows)
    _write_csv(event_csv, event_rows)
    audit = _audit(base_csv, event_csv)
    changed = any(abs(v) > EPS for v in audit["registered_deltas"].values())
    measurement = [
        GateResult("execution_valid", True, layer="R0", detail="state csv written"),
        GateResult(
            "unique_intervention_audit",
            audit["unique_path_ok"],
            layer="R0",
            detail="leaked " + ",".join(x["metric"] for x in audit["leaked_metrics"])
            if audit["leaked_metrics"]
            else "only registered path moved or nothing moved",
        ),
    ]
    # A leak is a measurement failure: we cannot attribute the Δ to the registered cause.
    artifact = [
        GateResult("comparison_rows_exist", bool(audit["rows"]), layer="R1", detail=f"n={len(audit['rows'])}"),
    ]
    criteria = [
        CriterionResult(
            criterion_id="registered_path_changed",
            layer="R2",
            scorer="rule",
            evaluable=audit["unique_path_ok"],
            score=1.0 if changed == expect_change else 0.0,
            passed=changed == expect_change,
            critical=True,
            evidence_ids=["mobility_intent"],
            detail=str(audit["registered_deltas"]),
        )
    ]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=criteria,
        extra=audit,
    )


def run() -> dict:
    shared = (
        _series("stress", 0.40, 0.50)
        + _series("emotion", 0.60, 0.50)
        + _series("mobility_intent", 0.30, 0.30)
    )
    unique_event = (
        _series("stress", 0.40, 0.50)
        + _series("emotion", 0.60, 0.50)
        + _series("mobility_intent", 0.30, 0.80)
    )
    spillover = (
        _series("stress", 0.40, 0.70)
        + _series("emotion", 0.60, 0.20)
        + _series("mobility_intent", 0.30, 0.80)
    )
    no_change = shared
    cells = [
        _score("unique_path_only", shared, unique_event, expect_change=True),
        _score("spillover_unregistered_metrics", shared, spillover, expect_change=True),
        _score("null_no_change", shared, no_change, expect_change=False),
    ]
    return summarize_workflow(WORKFLOW_ID, cells)
