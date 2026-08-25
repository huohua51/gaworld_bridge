"""Live GLM structured-action pairs under eval_mode contract.

The model must return JSON with target_action. Prose is not_evaluable.
"""

from __future__ import annotations

import json

from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "live_structured_pairs_001"
N_REPEATS = 3

PROMPTS = {
    "trust_reciprocity_scale_001": {
        "action": "submit_return",
        "field": "return_amount",
        "control": (
            "你是受托人。对方投入 10，倍率 3，你收到 30。"
            "登记规则：最低返还率 1.0，必须至少还本金 10。"
            "只输出 JSON：{\"target_action\":{\"action\":\"submit_return\",\"payload\":{\"return_amount\":<整数>}}}"
        ),
        "intervention": (
            "你是受托人。对方投入 10，倍率 3，你收到 30。"
            "登记规则：最低返还率 0.0，没有返还义务，允许还 0。"
            "只输出 JSON：{\"target_action\":{\"action\":\"submit_return\",\"payload\":{\"return_amount\":<整数>}}}"
        ),
    },
    "reservation_wage_apply_001": {
        "action": "evaluate_job_offer",
        "field": "decision",
        "control": (
            "你是求职孪生。保留工资 8000，到手月薪 9000，岗位仓储调度。"
            "规则：到手不低于保留工资才 accept，否则 reject。"
            "只输出 JSON：{\"target_action\":{\"action\":\"evaluate_job_offer\",\"payload\":{\"decision\":\"accept或reject\"}}}"
        ),
        "intervention": (
            "你是求职孪生。保留工资 8000，到手月薪 6500，岗位仓储调度。"
            "规则：到手不低于保留工资才 accept，否则 reject。"
            "只输出 JSON：{\"target_action\":{\"action\":\"evaluate_job_offer\",\"payload\":{\"decision\":\"accept或reject\"}}}"
        ),
    },
}


def _call(prompt: str) -> str:
    ensure_import_paths()
    from llm_providers import LLMRouter
    from config import CONFIG

    router = LLMRouter(CONFIG)
    return router.call(prompt, task="interview") or ""


def _score_once(repeat_id: int, suite: dict) -> dict:
    from gaworld.eval_mode import parse_structured_action
    from score_scale_rubrics import score_suite

    pairs: dict = {}
    raw_log: dict = {}
    for pair_id, spec in PROMPTS.items():
        pairs[pair_id] = {}
        raw_log[pair_id] = {}
        for variant in ("control", "intervention"):
            raw = _call(spec[variant])
            action = parse_structured_action(raw)
            pairs[pair_id][variant] = {"raw": raw, "target_action": action}
            raw_log[pair_id][variant] = {"raw": raw[:400], "parsed": action}
    report = score_suite(suite, {"batch_id": f"live_glm4_flash_r{repeat_id}", "pairs": pairs})
    coverage_ok = report["pair_coverage"] >= 0.9
    measurement = [
        GateResult("execution_valid", True, layer="R0", detail="live paratera GLM-4-Flash"),
        GateResult("pair_coverage", coverage_ok, layer="R0", detail=str(report["pair_coverage"])),
    ]
    artifact = [GateResult("target_action_present", report["evaluable_pairs"] > 0, layer="R1")]
    macro = report["macro_pair_accuracy"]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id=f"glm4_flash_live_r{repeat_id}",
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=[
            CriterionResult(
                criterion_id="macro_strict_pair",
                layer="R2",
                scorer="exact_pair",
                evaluable=macro is not None and coverage_ok,
                score=None if macro is None else float(macro),
                passed=macro == 1.0 if macro is not None else None,
                critical=True,
                evidence_ids=[item["pair_id"] for item in report["pairs"]],
                detail=json.dumps(raw_log, ensure_ascii=False)[:800],
            )
        ],
        extra={"score_suite": report, "raw": raw_log},
    )


def run() -> dict:
    ensure_import_paths()
    from score_scale_rubrics import load_json

    suite = load_json(BRIDGE_ROOT / "rubrics" / "suite_v0_1.json")
    cells = [_score_once(i, suite) for i in range(N_REPEATS)]
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["note"] = (
        "Live GLM-4-Flash via Paratera; capability Oracle, not Human Fidelity; "
        f"{N_REPEATS} repeats at temperature=0"
    )
    return summary
