#!/usr/bin/env python3
"""Hook the live Paratera LLM and start the official eval-mode tracks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow
from v0_first_batch.workflows import live_structured_pairs
from v0_first_batch.workflows.contract_interview import QUESTIONS


def _ping() -> dict:
    ensure_import_paths()
    from config import CONFIG
    from llm_providers import LLMRouter

    routing = CONFIG.get("llm", {}).get("routing", {})
    name = routing.get("default")
    model = ((CONFIG.get("llm") or {}).get("providers") or {}).get(name, {}).get("model")
    router = LLMRouter(CONFIG)
    reply = router.call("只回复一个字：好", task="interview")
    return {"provider": name, "model": model, "preview": (reply or "").strip()[:20], "ok": bool(reply)}


def _live_interview() -> dict:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    import pandas as pd
    import generative_city_sim as sim
    from gaworld.eval_mode import apply_eval_mode_runtime

    cfg = sim.CONFIG
    cfg.setdefault("eval_mode", {})
    cfg["eval_mode"]["enabled"] = True
    apply_eval_mode_runtime(cfg)
    sim.MD_PATH = str(GAWORLD_ROOT / "hangzhou_profiles_with_names.md")
    sim.CSV_PATH = str(GAWORLD_ROOT / "hangzhou_agents_state_init.csv")
    sim.MAP_PATH = str(GAWORLD_ROOT / "citymap.md")
    df = pd.read_csv(sim.CSV_PATH)
    agent = sim.build_agent(4, df, city_map=sim.load_city_map(sim.MAP_PATH))
    agent["memory"] = []
    answers = sim.interview_agent(agent, QUESTIONS, context="eval_mode live interview")
    n = len(QUESTIONS)
    texts = [str(item.get("answer") or "").strip() for item in answers]
    r1 = len(answers) == n and all(texts) and (n <= 1 or len(set(texts)) > 1)
    return compose(
        workflow_id="live_interview_contract_001",
        instance_id="agent4_eval_mode",
        measurement_gates=[GateResult("execution_valid", True, layer="R0", detail="live interview_agent")],
        artifact_gates=[
            GateResult("json_shape_1to1", len(answers) == n, layer="R1", detail=f"parsed={len(answers)}"),
            GateResult("no_identical_reuse", n <= 1 or len(set(texts)) > 1, layer="R1"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="each_question_answered",
                layer="R2",
                scorer="exact",
                evaluable=True,
                score=float(sum(1 for t in texts if t)) / n,
                passed=r1,
                critical=True,
                detail=json.dumps(answers, ensure_ascii=False)[:500],
            )
        ],
        extra={"answers": answers},
    )


def _start_eval_mode_sim(out: Path) -> dict:
    sim_dir = out / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    overrides = {
        "agent_ids": [4, 5],
        "sim_days": 1,
        "stateful": False,
        "simulate_realtime": False,
        "seconds_per_day": 1,
        "eval_mode": {
            "enabled": True,
            "disable_dynamic_behavior": True,
            "disable_routine_change": True,
            "disable_diary_fallback": True,
            "strict_interview_json": True,
            "write_run_manifest": True,
        },
        "dynamic_behavior": {"enabled": False},
        "routine_change": {"enabled": False},
        "news": {"enabled": False, "info_seek": {"enabled": False}},
        "intervention": {"enabled": False},
        "distributed": {"enabled": False},
        "visualization": {"enabled": False},
        "life_events": {"enabled": False},
        "external_rag": {"bootstrap": {"enabled": False}},
        "llm": {
            "routing": {
                "default": "paratera_glm",
                "tasks": {"schedule": "paratera_glm"},
            }
        },
        "memory_dir": str(sim_dir / "memory"),
        "log_dir": str(sim_dir / "logs"),
        "state_output_dir": str(sim_dir / "state"),
        "diary_output_dir": str(sim_dir / "diaries"),
        "network_output_dir": str(sim_dir / "network"),
        "environment_output_dir": str(sim_dir / "environment"),
    }
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["GAWORLD_LLM_PROVIDER"] = "paratera_glm"
    env["GAWORLD_CONFIG_OVERRIDES"] = json.dumps(overrides, ensure_ascii=False)
    log_path = sim_dir / "run.log"
    log_f = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "generative_city_sim.py", "run", "--eval-mode"],
        cwd=str(GAWORLD_ROOT),
        env=env,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
    )
    meta = {
        "pid": proc.pid,
        "cwd": str(GAWORLD_ROOT),
        "log": str(log_path),
        "overrides": overrides,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    (sim_dir / "launch.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    ensure_import_paths()
    out = BRIDGE_ROOT / "output" / "live_run_20260823"
    out.mkdir(parents=True, exist_ok=True)
    ping = _ping()
    print(f"LLM ping provider={ping['provider']} model={ping['model']} preview={ping['preview']!r}")
    pairs = live_structured_pairs.run()
    (out / "live_structured_pairs_001.json").write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "pairs coverage={coverage} full_pass_rate={full_pass_rate} mean_task_score={mean_task_score}".format(
            **{k: pairs.get(k) for k in ("coverage", "full_pass_rate", "mean_task_score")}
        )
    )
    interview = summarize_workflow("live_interview_contract_001", [_live_interview()])
    (out / "live_interview_contract_001.json").write_text(
        json.dumps(interview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "interview coverage={coverage} full_pass_rate={full_pass_rate}".format(
            coverage=interview.get("coverage"),
            full_pass_rate=interview.get("full_pass_rate"),
        )
    )
    launch = _start_eval_mode_sim(out)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ping": ping,
        "pairs": pairs,
        "interview": interview,
        "sim_launch": launch,
        "note": "City sim is running in background under eval_mode; pairs/interview are capability Oracle.",
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"eval_mode sim started pid={launch['pid']} log={launch['log']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
