"""W8: 1-day / 2-agent mock-LLM smoke as Execution Validity, not model ability."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from v0_first_batch.paths import GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "sim_smoke_mock_llm_001"


def run() -> dict:
    ensure_import_paths()
    import generative_city_sim as sim
    from config import CONFIG
    from tests.fixtures.mock_llm import install

    tmp = tempfile.mkdtemp(prefix="gaw_smoke_")
    original_cwd = os.getcwd()
    originals: dict[str, object] = {}
    try:
        for name in (
            "hangzhou_agents_state_init.csv",
            "hangzhou_profiles_with_names.md",
            "citymap.md",
            "news_source.md",
            "news_cache.json",
        ):
            src = GAWORLD_ROOT / name
            if src.exists():
                shutil.copy(src, Path(tmp) / name)
        os.chdir(tmp)
        keys = (
            "agent_ids",
            "sim_days",
            "stateful",
            "simulate_realtime",
            "seconds_per_day",
            "news",
            "human_realism",
            "intervention",
            "external_environment_service",
            "distributed",
            "visualization",
            "life_events",
            "external_rag",
            "dynamic_behavior",
        )
        for key in keys:
            if key in CONFIG:
                originals[key] = CONFIG[key]
        CONFIG["agent_ids"] = [4, 5]
        CONFIG["sim_days"] = 1
        CONFIG["stateful"] = False
        CONFIG["simulate_realtime"] = False
        CONFIG["seconds_per_day"] = 1
        if isinstance(CONFIG.get("news"), dict):
            CONFIG["news"] = dict(CONFIG["news"])
            CONFIG["news"]["enabled"] = False
            CONFIG["news"]["info_seek"] = dict(CONFIG["news"].get("info_seek", {}))
            CONFIG["news"]["info_seek"]["enabled"] = False
        if isinstance(CONFIG.get("external_rag"), dict):
            CONFIG["external_rag"] = dict(CONFIG["external_rag"])
            CONFIG["external_rag"]["bootstrap"] = dict(CONFIG["external_rag"].get("bootstrap", {}))
            CONFIG["external_rag"]["bootstrap"]["enabled"] = False
        if isinstance(CONFIG.get("intervention"), dict):
            CONFIG["intervention"] = dict(CONFIG["intervention"])
            CONFIG["intervention"]["enabled"] = False
        if isinstance(CONFIG.get("external_environment_service"), dict):
            CONFIG["external_environment_service"] = dict(CONFIG["external_environment_service"])
            CONFIG["external_environment_service"]["enabled"] = False
        if isinstance(CONFIG.get("distributed"), dict):
            CONFIG["distributed"] = dict(CONFIG["distributed"])
            CONFIG["distributed"]["enabled"] = False
        if isinstance(CONFIG.get("visualization"), dict):
            CONFIG["visualization"] = dict(CONFIG["visualization"])
            CONFIG["visualization"]["enabled"] = False
        if isinstance(CONFIG.get("life_events"), dict):
            CONFIG["life_events"] = dict(CONFIG["life_events"])
            CONFIG["life_events"]["enabled"] = False
        if isinstance(CONFIG.get("dynamic_behavior"), dict):
            CONFIG["dynamic_behavior"] = dict(CONFIG["dynamic_behavior"])
            CONFIG["dynamic_behavior"]["enabled"] = False
        if isinstance(CONFIG.get("human_realism"), dict):
            CONFIG["human_realism"] = dict(CONFIG["human_realism"])
            CONFIG["human_realism"]["enabled"] = False

        sim.AGENT_IDS = [4, 5]
        sim.SIM_DAYS = 1
        sim.STATEFUL = False
        sim.SIMULATE_REALTIME = False
        sim.SECONDS_PER_DAY = 1
        sim.NEWS_ENABLED = False
        sim.INTERVENTION_ENABLED = False
        sim.HUMAN_REALISM_ENABLED = False
        sim.VISUALIZATION_ENABLED = False
        sim.LIFE_EVENTS_ENABLED = False

        error = None
        seen: list[str] = []
        with install() as mock:
            try:
                sim.run_simulation()
                seen = list(mock.tasks_seen())
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"

        log_dir = Path(tmp) / "output" / "logs"
        logs = {
            aid: (log_dir / f"agent_{aid}.log").exists()
            and (log_dir / f"agent_{aid}.log").stat().st_size > 0
            for aid in (4, 5)
        }
        output_tree = []
        out_root = Path(tmp) / "output"
        if out_root.exists():
            for path in sorted(out_root.rglob("*")):
                if path.is_file():
                    output_tree.append(str(path.relative_to(tmp)))
        finished = error is None
        logs_ok = all(logs.values())
        measurement = [
            GateResult("execution_valid", finished, layer="R0", detail=error or "run_simulation returned"),
            GateResult("trace_logs_present", logs_ok, layer="R0", detail=str(logs)),
        ]
        artifact = [
            GateResult("per_agent_log_nonempty", logs_ok, layer="R1", detail=str(logs)),
        ]
        routine_ok = bool(set(seen) & {"schedule", "daily_routine"})
        step_ok = bool(set(seen) & {"planning", "reflection", "perception", "daily_diary"})
        criteria = [
            CriterionResult(
                criterion_id="canonical_llm_tasks_dispatched",
                layer="R2",
                scorer="set",
                evaluable=finished,
                score=1.0 if routine_ok and step_ok else 0.0,
                passed=routine_ok and step_ok,
                critical=True,
                evidence_ids=sorted(set(seen)),
                detail=f"tasks={sorted(set(seen))}",
            )
        ]
        cell = compose(
            workflow_id=WORKFLOW_ID,
            instance_id="seed_agents_4_5_day1_mock",
            measurement_gates=measurement,
            artifact_gates=artifact,
            criteria=criteria,
            extra={
                "tasks_seen": sorted(set(seen)),
                "output_files": output_tree[:80],
                "output_file_count": len(output_tree),
                "workdir": tmp,
                "note": "Mock LLM Execution Validity only; not a model ranking cell",
            },
        )
        cell["ranking_eligible"] = False
        summary = summarize_workflow(WORKFLOW_ID, [cell])
        summary["ranking_eligible"] = False
        summary["status"] = "calibration"
        return summary
    finally:
        os.chdir(original_cwd)
        for key, value in originals.items():
            CONFIG[key] = value
