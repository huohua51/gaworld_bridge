"""Score a finished eval-mode city run from sealed artifacts.

This is Execution / Contract evidence for one city_run, not Task Competence.
R2 stays not_enabled: the 1-day Hangzhou run has no Oracle.
"""

from __future__ import annotations

import json
from pathlib import Path

from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "live_eval_mode_city_run_001"
DEFAULT_SIM = (
    Path(__file__).resolve().parents[2] / "output" / "live_run_20260823" / "sim"
)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _log_text(sim_dir: Path) -> str:
    log = sim_dir / "run.log"
    return log.read_text(encoding="utf-8") if log.is_file() else ""


def score_sim(sim_dir: Path | None = None) -> dict:
    sim_dir = Path(sim_dir or DEFAULT_SIM)
    manifest = _read_json(sim_dir / "run_manifest.json")
    launch = _read_json(sim_dir / "launch.json")
    log = _log_text(sim_dir)
    eval_block = manifest.get("eval_mode") or {}
    diaries = {
        "agent_4": sim_dir / "diaries" / "agent_4" / "day_001.md",
        "agent_5": sim_dir / "diaries" / "agent_5" / "day_001.md",
    }
    diary_chars = {
        key: path.read_text(encoding="utf-8") if path.is_file() else ""
        for key, path in diaries.items()
    }
    state_csv = sim_dir / "state" / "agent_state_history.csv"
    state_rows = 0
    if state_csv.is_file():
        state_rows = max(0, sum(1 for _ in state_csv.open(encoding="utf-8")) - 1)
    fallback_hits = [
        line for line in log.splitlines()
        if "using fallback" in line or "diary fallback" in line.lower()
    ]
    process_done = "✅ 模拟完成" in log
    eval_on = bool(eval_block.get("enabled"))
    dyn_off = manifest.get("dynamic_behavior_enabled") is False
    routine_off = manifest.get("routine_change_enabled") is False
    diaries_ok = all(len(text.strip()) >= 200 for text in diary_chars.values())

    measurement = [
        GateResult("execution_valid", process_done, layer="R0", detail="run.log has 模拟完成"),
        GateResult("run_manifest_present", bool(eval_block), layer="R0", detail=str(sim_dir / "run_manifest.json")),
        GateResult("eval_mode_enabled", eval_on, layer="R0", detail=json.dumps(eval_block, ensure_ascii=False)),
    ]
    artifact = [
        GateResult("dynamic_behavior_off", dyn_off, layer="R1", detail=str(manifest.get("dynamic_behavior_enabled"))),
        GateResult("routine_change_off", routine_off, layer="R1", detail=str(manifest.get("routine_change_enabled"))),
        GateResult(
            "diaries_nonempty",
            diaries_ok,
            layer="R1",
            detail=json.dumps({k: len(v) for k, v in diary_chars.items()}, ensure_ascii=False),
        ),
        GateResult("state_csv_present", state_rows > 0, layer="R1", detail=f"rows={state_rows}"),
        GateResult("no_diary_fallback_in_log", not fallback_hits, layer="R1", detail=str(fallback_hits[:3])),
    ]
    criteria = [
        CriterionResult(
            criterion_id="city_run_execution_only",
            layer="R2",
            scorer="not_enabled",
            evaluable=False,
            score=None,
            passed=None,
            critical=False,
            detail="No Oracle / target action on this 1-day city_run; do not upgrade to TaskScore",
        )
    ]
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id="live_run_20260823_agents_4_5_day1",
        measurement_gates=measurement,
        artifact_gates=artifact,
        criteria=criteria,
        extra={
            "sim_dir": str(sim_dir),
            "started_at": launch.get("started_at"),
            "manifest_generated_at": manifest.get("generated_at"),
            "agent_ids": manifest.get("agent_ids"),
            "sim_days": manifest.get("sim_days"),
            "diary_chars": {k: len(v) for k, v in diary_chars.items()},
            "state_rows": state_rows,
            "attribution": {
                "agent_caused_success": "not_enabled",
                "environment_assisted_success": "not_enabled",
                "system_success": process_done and diaries_ok,
                "reason": "override event stream not written; only disable-flags + refused fallback",
            },
        },
    )
    # Execution validity is not a capability ranking result.
    cell["ranking_eligible"] = False
    return cell


def run(sim_dir: Path | None = None) -> dict:
    cell = score_sim(sim_dir)
    summary = summarize_workflow(WORKFLOW_ID, [cell])
    summary["ranking_eligible"] = False
    summary["note"] = (
        "Sealed eval_mode city_run. P0/R1 only. "
        "No Oracle, no attribution split, not a model leaderboard."
    )
    return summary
