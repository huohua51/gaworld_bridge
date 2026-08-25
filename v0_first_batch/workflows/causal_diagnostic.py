"""W4: existing scale-rubric Probe suite (Causal Diagnostic Suite seed)."""

from __future__ import annotations

from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "causal_diagnostic_suite_001"


def _score_batch(batch_id: str, traces: dict, suite: dict) -> dict:
    ensure_import_paths()
    from score_scale_rubrics import score_suite

    report = score_suite(suite, traces)
    coverage_ok = report["pair_coverage"] >= 0.9
    measurement = [
        GateResult("execution_valid", True, layer="R0", detail=f"batch={batch_id}"),
        GateResult(
            "pair_coverage",
            coverage_ok,
            layer="R0",
            detail=f"coverage={report['pair_coverage']}",
        ),
    ]
    artifact = [
        GateResult("target_action_present", report["evaluable_pairs"] > 0, layer="R1"),
    ]
    macro = report["macro_pair_accuracy"]
    criteria = [
        CriterionResult(
            criterion_id="macro_strict_pair",
            layer="R2",
            scorer="exact_pair",
            evaluable=macro is not None and coverage_ok,
            score=None if macro is None else float(macro),
            passed=macro == 1.0 if macro is not None else None,
            critical=True,
            evidence_ids=[p["pair_id"] for p in report["pairs"]],
            detail=f"ranking_eligible={report['ranking_eligible']}",
        )
    ]
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=batch_id,
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=criteria,
        extra=report,
    )
    if not coverage_ok:
        cell["ranking_eligible"] = False
        cell["status"] = "measurement_invalid"
        cell["measurement_valid"] = False
        cell["full_pass"] = None
        cell["task_score"] = None
    return cell


def run() -> dict:
    ensure_import_paths()
    from score_scale_rubrics import load_json

    suite = load_json(BRIDGE_ROOT / "rubrics" / "suite_v0_1.json")
    capable = load_json(BRIDGE_ROOT / "fixtures" / "capable_traces.json")
    locked = load_json(BRIDGE_ROOT / "fixtures" / "locked_yes_traces.json")
    missing = {
        "batch_id": "missing_target_action",
        "pairs": {
            "trust_reciprocity_scale_001": {
                "control": {"interview": "我说我很信任。"},
                "intervention": {"interview": "我还是很信任。"},
            },
            "reservation_wage_apply_001": {
                "control": {"target_action": {"payload": {"decision": "accept"}}},
                "intervention": {"target_action": {"payload": {"decision": "reject"}}},
            },
        },
    }
    cells = [
        _score_batch("capable_traces", capable, suite),
        _score_batch("locked_yes_traces", locked, suite),
        _score_batch("missing_target_action", missing, suite),
    ]
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["note"] = (
        "WorkDiag 18 + SocietyDiag 16 pairs remain an external Causal Diagnostic "
        "Suite; they are not re-run inside GAWorld this batch."
    )
    return summary
