"""W5: HumanScore uses mock data — keep the number, lock ranking."""

from __future__ import annotations

import importlib.util
import inspect

from v0_first_batch.paths import GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "life_history_mock_score_001"


def _load_evaluator_class():
    path = GAWORLD_ROOT / "eval" / "life_history_eval.py"
    spec = importlib.util.spec_from_file_location("life_history_eval_module", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LifeHistoryEvaluator


def run() -> dict:
    ensure_import_paths()
    from gaworld.core.life_history.mock_data import create_mock_scores
    from generative_city_sim import __file__ as sim_file

    LifeHistoryEvaluator = _load_evaluator_class()
    scores = create_mock_scores()
    evaluator = LifeHistoryEvaluator(52)
    source = inspect.getsource(LifeHistoryEvaluator.__init__)
    uses_mock = "create_mock_scores" in source or evaluator.mock_scores == scores
    sim_text = open(sim_file, encoding="utf-8").read()
    engine_wired = "LifeHistoryEngine" in sim_text or "create_life_history_engine" in sim_text

    measurement = [
        GateResult(
            "human_reference_eligibility",
            False,
            layer="R0",
            detail="scores come from create_mock_scores(), not a matched human sample",
        ),
        GateResult(
            "trace_bound_scorer",
            False,
            layer="R0",
            detail="LifeHistoryEvaluator does not read canonical_trace",
        ),
        GateResult(
            "engine_in_main_loop",
            engine_wired,
            layer="R0",
            detail="LifeHistoryEngine referenced in generative_city_sim.py"
            if engine_wired
            else "LifeHistoryEngine is not wired into the main simulator",
        ),
    ]
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id="agent52_mock_humanscore",
        measurement_gates=measurement,
        artifact_gates=[],
        criteria=[
            CriterionResult(
                criterion_id="mock_score_detected",
                layer="R2",
                scorer="rule",
                evaluable=False,
                score=None,
                detail="raw HumanScore retained as diagnostic only",
            )
        ],
        extra={
            "mock_scores": scores,
            "uses_mock": uses_mock,
            "engine_wired": engine_wired,
            "ranking_eligible": False,
        },
    )
    cell["ranking_eligible"] = False
    summary = summarize_workflow(WORKFLOW_ID, [cell])
    summary["ranking_eligible"] = False
    summary["human_fidelity_status"] = "diagnostic"
    return summary
