"""W9: reservation-wage / trust pairs via GAWorld structured-action parse.

Uses the same Oracle suite as the Causal Diagnostic seed. Mock LLM only —
not a live model ranking cell.
"""

from __future__ import annotations

from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "structured_action_pairs_001"

MOCK_CAPABLE = {
    "trust_reciprocity_scale_001": {
        "control": '{"target_action":{"action":"submit_return","payload":{"return_amount":10}}}',
        "intervention": '{"target_action":{"action":"submit_return","payload":{"return_amount":0}}}',
    },
    "reservation_wage_apply_001": {
        "control": '{"target_action":{"action":"evaluate_job_offer","payload":{"decision":"accept"}}}',
        "intervention": '{"target_action":{"action":"evaluate_job_offer","payload":{"decision":"reject"}}}',
    },
}
MOCK_LOCKED = {
    "trust_reciprocity_scale_001": {
        "control": '{"target_action":{"action":"submit_return","payload":{"return_amount":10}}}',
        "intervention": '{"target_action":{"action":"submit_return","payload":{"return_amount":10}}}',
    },
    "reservation_wage_apply_001": {
        "control": '{"target_action":{"action":"evaluate_job_offer","payload":{"decision":"accept"}}}',
        "intervention": '{"target_action":{"action":"evaluate_job_offer","payload":{"decision":"accept"}}}',
    },
}


def _batch_from_mock(batch_id: str, mock: dict) -> dict:
    ensure_import_paths()
    from gaworld.eval_mode import parse_structured_action

    pairs = {}
    for pair_id, variants in mock.items():
        pairs[pair_id] = {}
        for variant, text in variants.items():
            action = parse_structured_action(text)
            pairs[pair_id][variant] = {
                "raw": text,
                "target_action": action,
            }
    return {"batch_id": batch_id, "pairs": pairs}


def _score(instance_id: str, mock: dict, suite: dict) -> dict:
    ensure_import_paths()
    from score_scale_rubrics import score_suite

    traces = _batch_from_mock(instance_id, mock)
    report = score_suite(suite, traces)
    coverage_ok = report["pair_coverage"] >= 0.9
    measurement = [
        GateResult("execution_valid", True, layer="R0", detail="parse_structured_action"),
        GateResult("pair_coverage", coverage_ok, layer="R0", detail=str(report["pair_coverage"])),
    ]
    artifact = [GateResult("target_action_present", report["evaluable_pairs"] > 0, layer="R1")]
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
            evidence_ids=[item["pair_id"] for item in report["pairs"]],
        )
    ]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=criteria,
        extra=report,
    )


def run() -> dict:
    ensure_import_paths()
    from score_scale_rubrics import load_json

    suite = load_json(BRIDGE_ROOT / "rubrics" / "suite_v0_1.json")
    cells = [
        _score("capable_structured_json", MOCK_CAPABLE, suite),
        _score("locked_structured_json", MOCK_LOCKED, suite),
        _score(
            "prose_no_action",
            {
                "trust_reciprocity_scale_001": {"control": "我很信任。", "intervention": "我还是信任。"},
                "reservation_wage_apply_001": {"control": "有工作就接。", "intervention": "有工作就接。"},
            },
            suite,
        ),
    ]
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    summary["note"] = "Mock structured JSON through gaworld.eval_mode.parse_structured_action; not a live model cell"
    return summary
