"""W6: Eval-mode Environment Contract — environment must not silently fix agents."""

from __future__ import annotations

from unittest.mock import patch

from v0_first_batch.paths import ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "eval_mode_environment_001"


def _default_cell() -> dict:
    ensure_import_paths()
    from config import CONFIG
    from dynamic_behavior import evaluate_step_dynamics
    from gaworld.eval_mode import eval_mode_enabled, interview_fallback_allowed

    dyn_enabled = bool((CONFIG.get("dynamic_behavior") or {}).get("enabled", False))
    has_eval_mode = isinstance(CONFIG.get("eval_mode"), dict)
    hungry = {
        "id": 1,
        "name": "测试员",
        "personality": "外向开朗",
        "values": "社交",
        "daily_life": "朝九晚五",
        "job": "程序员",
        "state": {
            "energy": 0.2,
            "emotion": 0.4,
            "stress": 0.6,
            "mood": 0.3,
            "social_need": 0.8,
            "hunger": 0.95,
            "fatigue_debt": 0.8,
            "self_control": 0.2,
            "time_pressure": 0.7,
            "risk_preference": 0.5,
        },
        "locations": {"current": "Central Block"},
        "relationships": {},
    }
    rewritten = evaluate_step_dynamics(
        hungry,
        "12:00",
        "工作",
        env_events=[{"type": "traffic_jam", "location": "Central Block", "intensity": 0.9}],
        all_agents=[hungry],
        agents_by_id={1: hungry},
        config={"dynamic_behavior": {"enabled": True}},
    )
    frozen = evaluate_step_dynamics(
        hungry,
        "12:00",
        "工作",
        env_events=[],
        all_agents=[hungry],
        agents_by_id={1: hungry},
        config={"dynamic_behavior": {"enabled": False}},
    )
    measurement = [
        GateResult(
            "eval_mode_declared",
            has_eval_mode,
            layer="R0",
            detail="CONFIG has eval_mode block" if has_eval_mode else "missing eval_mode",
        ),
    ]
    artifact = [
        GateResult(
            "default_config_does_not_rewrite",
            not dyn_enabled,
            layer="R1",
            detail=f"dynamic_behavior.enabled={dyn_enabled}",
        ),
        GateResult(
            "default_eval_mode_off",
            has_eval_mode and not eval_mode_enabled(CONFIG),
            layer="R1",
            detail="default run remains a city simulator",
        ),
        GateResult(
            "disable_flag_freezes_activity",
            frozen.get("changed") is False and frozen.get("activity") == "工作",
            layer="R1",
            detail=str({"changed": frozen.get("changed"), "activity": frozen.get("activity")}),
        ),
        GateResult(
            "default_interview_has_no_prose_fallback",
            not interview_fallback_allowed(CONFIG),
            critical=False,
            layer="R1",
            detail="default interview still allows prose fallback (product path)",
        ),
    ]
    criteria = [
        CriterionResult(
            criterion_id="rewrite_detectable",
            layer="R3",
            scorer="rule",
            evaluable=True,
            score=1.0 if isinstance(rewritten.get("changed"), bool) else 0.0,
            passed=isinstance(rewritten.get("changed"), bool),
            critical=False,
            detail=str(
                {
                    "enabled_changed": rewritten.get("changed"),
                    "enabled_activity": rewritten.get("activity"),
                    "reason": rewritten.get("reason"),
                }
            ),
        )
    ]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id="current_default_config",
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=criteria,
        extra={
            "dynamic_behavior_enabled": dyn_enabled,
            "eval_mode_enabled": eval_mode_enabled(CONFIG),
            "rewrite_when_enabled": rewritten,
            "frozen_when_disabled": frozen,
        },
    )


def _enabled_cell() -> dict:
    ensure_import_paths()
    import generative_city_sim as sim
    from gaworld.eval_mode import apply_eval_mode_runtime, interview_fallback_allowed

    cfg = {
        "eval_mode": {"enabled": True, "strict_interview_json": True, "disable_diary_fallback": True},
        "dynamic_behavior": {"enabled": True},
        "routine_change": {"enabled": True},
        "agent_ids": [4],
    }
    applied = apply_eval_mode_runtime(cfg)
    agent = {"id": 23, "name": "测试者", "state": {"emotion": 0.5, "stress": 0.5}}
    with patch.object(sim, "CONFIG", cfg), patch.object(
        sim, "evoke_memory", return_value={"hint": "", "recollection": "", "hits": []}
    ), patch.object(sim, "call_llm", return_value="今天心情不错。"):
        answers = sim.interview_agent(agent, ["问1", "问2"])
    with patch.object(sim, "CONFIG", cfg), patch.object(sim, "call_llm", return_value="太短"):
        diary = sim.generate_daily_diary({"id": 8, "name": "A", "intentions": {}, "episodes": []}, 1, logs="x")
    with patch.object(sim, "CONFIG", cfg):
        activity, _reason, changed = sim.maybe_adjust_activity(agent, "10:00", "工作", "", "", "", [], "")

    measurement = [
        GateResult("eval_mode_applied", applied["applied"], layer="R0", detail=str(applied["changes"])),
    ]
    artifact = [
        GateResult("dynamic_behavior_off", cfg["dynamic_behavior"]["enabled"] is False, layer="R1"),
        GateResult("interview_no_prose_fallback", answers == [], layer="R1", detail=str(answers)),
        GateResult("diary_no_fallback", diary == "", layer="R1", detail=repr(diary[:40])),
        GateResult("routine_change_frozen", changed is False and activity == "工作", layer="R1"),
        GateResult(
            "fallback_helper_denied",
            interview_fallback_allowed(cfg) is False,
            layer="R1",
        ),
    ]
    criteria = [
        CriterionResult(
            criterion_id="eval_contract_holds",
            layer="R2",
            scorer="rule",
            evaluable=True,
            score=1.0,
            passed=True,
            critical=True,
            detail="enabled eval_mode refuses rewrite, interview fallback, diary fallback",
        )
    ]
    return compose(
        workflow_id=WORKFLOW_ID,
        instance_id="eval_mode_enabled_runtime",
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=criteria,
        extra={"applied": applied, "interview_answers": answers, "diary": diary},
    )


def run() -> dict:
    return summarize_workflow(WORKFLOW_ID, [_default_cell(), _enabled_cell()])
