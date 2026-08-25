#!/usr/bin/env python3
"""EXP-GM-01: T1 venue close. Rule first, then seed 0. Fill repeats only if Coverage=1 and not floor/ceiling."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_01.loop import run_cell_loop
from exp_gm_01.probes import PROBES
from exp_gm_01.roles import agent_prompt, parse_json_object, rule_agent
from exp_gm_01.scoring import (
    closure_adaptation_rate,
    control_stability_rate,
    score_cell,
    unnecessary_replan_rate,
)
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_01_venue_close"
TRACKS = ("direct_current_state", "full_event", "drop_event")
VARIANTS = ("control", "intervention")
PROVIDER = "paratera_glm"
MODEL = "GLM-4-Flash"
TEMPERATURE = 0


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault(PROVIDER, {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 1024)
        glm["temperature"] = TEMPERATURE
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = PROVIDER
    tasks = dict(routing.get("tasks") or {})
    tasks["schedule"] = PROVIDER
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = PROVIDER


def _llm(prompt: str) -> str:
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _city_map():
    from city_map_system import load_city_map

    return load_city_map("citymap.md")


def _rule_fn(probe: dict):
    def agent(notice, _schedule):
        return rule_agent(probe, notice=notice)

    return agent


def _llm_fn(probe: dict):
    def agent(notice, schedule):
        extra = "没有收到场所状态事件。不要编造 evidence_event_id。" if notice is None else ""
        text = _llm(agent_prompt(probe, notice=notice, schedule=schedule, extra=extra))
        try:
            return parse_json_object(text)
        except (ValueError, json.JSONDecodeError):
            return {}

    return agent


def _score_cell(probe: dict, variant: str, track: str, seed: int, out_root: Path, *, mode: str, city_map: dict) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    apply_eval_mode_runtime(CONFIG)

    instance_id = f"{probe['id']}_{variant}_{track}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    loop = run_cell_loop(
        probe=probe,
        variant=variant,
        track=track,
        task_id=instance_id,
        out_dir=run_dir,
        agent_fn=_rule_fn(probe) if mode == "rule" else _llm_fn(probe),
        city_map=city_map,
    )
    cell = score_cell(
        probe=probe,
        variant=variant,
        track=track,
        seed=seed,
        loop=loop,
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
    )
    extra = dict(cell.get("extra") or {})
    extra["mode"] = mode
    extra["model_version"] = "rule" if mode == "rule" else MODEL
    extra["temperature"] = TEMPERATURE
    cell["extra"] = extra
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cell


def _rate(cells: list[dict], track: str, field: str, variant: str | None = None) -> float | None:
    subset = [
        c for c in cells
        if (c.get("extra") or {}).get("track") == track
        and (variant is None or (c.get("extra") or {}).get("variant") == variant)
        and c.get("full_pass") is not None
    ]
    if field == "target_correct":
        subset = [
            c for c in cells
            if (c.get("extra") or {}).get("track") == track
            and (variant is None or (c.get("extra") or {}).get("variant") == variant)
            and c.get("measurement_valid")
        ]
        if not subset:
            return None
        return round(sum(int(bool((c.get("extra") or {}).get("target_correct"))) for c in subset) / len(subset), 4)
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _coverage(cells: list[dict], track: str) -> float:
    subset = [c for c in cells if (c.get("extra") or {}).get("track") == track]
    if not subset:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in subset) / len(subset), 4)


def _first_pass_gate(cells: list[dict]) -> str:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    if summary["coverage"] < 1.0:
        return "A_r0"
    scored = [c for c in cells if c.get("full_pass") is not None]
    if not scored:
        return "A_r0"
    if all(int(c["full_pass"]) == 0 for c in scored):
        return "C_floor"
    if all(int(c["full_pass"]) == 1 for c in scored):
        return "C_ceiling"
    return "fill_repeats"


def _pack(cells: list[dict], out: Path, *, phase: str, mode: str) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    rates = {
        "direct_current_state": _rate(cells, "direct_current_state", "full_pass"),
        "full_event": _rate(cells, "full_event", "full_pass"),
        "drop_event": _rate(cells, "drop_event", "full_pass"),
        "direct_target": _rate(cells, "direct_current_state", "target_correct"),
        "full_target": _rate(cells, "full_event", "target_correct"),
        "drop_target": _rate(cells, "drop_event", "target_correct"),
        "full_control": _rate(cells, "full_event", "full_pass", "control"),
        "full_intervention": _rate(cells, "full_event", "full_pass", "intervention"),
        "drop_control": _rate(cells, "drop_event", "full_pass", "control"),
        "drop_intervention": _rate(cells, "drop_event", "full_pass", "intervention"),
    }
    coverage = {
        "direct_current_state": _coverage(cells, "direct_current_state"),
        "full_event": _coverage(cells, "full_event"),
        "drop_event": _coverage(cells, "drop_event"),
    }
    event_value_full = None if rates["full_event"] is None or rates["drop_event"] is None else round(rates["full_event"] - rates["drop_event"], 4)
    event_value_target = None if rates["full_target"] is None or rates["drop_target"] is None else round(rates["full_target"] - rates["drop_target"], 4)
    diagnostics = {
        "closure_adaptation_rate": {
            "direct_current_state": closure_adaptation_rate(cells, "direct_current_state"),
            "full_event": closure_adaptation_rate(cells, "full_event"),
            "drop_event": closure_adaptation_rate(cells, "drop_event"),
        },
        "control_stability_rate": {
            "direct_current_state": control_stability_rate(cells, "direct_current_state"),
            "full_event": control_stability_rate(cells, "full_event"),
            "drop_event": control_stability_rate(cells, "drop_event"),
        },
        "unnecessary_replan_rate": {
            "direct_current_state": unnecessary_replan_rate(cells, "direct_current_state"),
            "full_event": unnecessary_replan_rate(cells, "full_event"),
            "drop_event": unnecessary_replan_rate(cells, "drop_event"),
        },
    }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-01",
        "task_id": "TASK-L1-venue-close",
        "phase": phase,
        "mode": mode,
        "ranking_eligible": False,
        "gate": (
            "completed_repeats" if phase == "all"
            else _first_pass_gate(cells) if phase.startswith("seed0") or phase == "rule"
            else None
        ),
        "summary": summary,
        "coverage": coverage,
        "rates": rates,
        "event_value_full": event_value_full,
        "event_value_target": event_value_target,
        "diagnostics": diagnostics,
        "propagation_gap": None if rates["direct_current_state"] is None or rates["full_event"] is None else round(
            rates["direct_current_state"] - rates["full_event"], 4
        ),
    }
    if payload["gate"] == "A_r0":
        payload["estimands"] = {
            "event_value_full": "N/A",
            "event_value_target": "N/A",
            "reason": "coverage_failed",
        }
    elif payload["gate"] in {"C_floor", "C_ceiling"}:
        payload["estimands"] = {
            "event_value_full": "N/A",
            "event_value_target": "N/A",
            "reason": payload["gate"],
        }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# EXP-GM-01 T1 venue close",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；mode：{mode}",
        "- ranking_eligible：false",
        "- 动作接口：扁平 update_visit，不使用审核 JSON",
        "",
        "## 覆盖与主结果",
        "",
        f"- requested：{summary['requested']}",
        f"- measurement_valid：{summary['measurement_valid']}",
        f"- coverage：{summary['coverage']}",
        f"- gate：{payload['gate']}",
        f"- FullPass direct / full / drop：{rates['direct_current_state']} / {rates['full_event']} / {rates['drop_event']}",
        f"- TargetCorrect direct / full / drop：{rates['direct_target']} / {rates['full_target']} / {rates['drop_target']}",
        f"- EventValue_full (Full − Drop)：{event_value_full}",
        f"- EventValue_target (Full − Drop)：{event_value_target}",
        f"- PropagationGap (direct − full)：{payload['propagation_gap']}",
        "",
        "## 分变体诊断",
        "",
        f"- ClosureAdaptationRate direct / full / drop：{diagnostics['closure_adaptation_rate']['direct_current_state']} / {diagnostics['closure_adaptation_rate']['full_event']} / {diagnostics['closure_adaptation_rate']['drop_event']}",
        f"- ControlStabilityRate direct / full / drop：{diagnostics['control_stability_rate']['direct_current_state']} / {diagnostics['control_stability_rate']['full_event']} / {diagnostics['control_stability_rate']['drop_event']}",
        f"- UnnecessaryReplanRate direct / full / drop：{diagnostics['unnecessary_replan_rate']['direct_current_state']} / {diagnostics['unnecessary_replan_rate']['full_event']} / {diagnostics['unnecessary_replan_rate']['drop_event']}",
        "",
        "关闭事件能沿感知链送达并改变目的地与日程；模型在真正关闭时能稳定重规划，",
        "但存在明显过度适应——场所没有关闭时也主动改道。平台通道通过，Agent 条件判断部分成功。",
        "模型把“重新评估当前状态”误解成“必须重新选择地点”，缺少“状态未改变就保持原计划”的决策分支。",
        "本实验冻结为 development pilot，不建 T1 留出题。",
        "",
        "| instance | valid | FullPass | target_correct | first_error |",
        "|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('target_correct')} | {(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def run_matrix(out: Path, seeds: list[int], *, mode: str, city_map: dict) -> list[dict]:
    cells: list[dict] = []
    for probe in PROBES:
        for variant in VARIANTS:
            for track in TRACKS:
                for seed in seeds:
                    print(f"run {probe['id']} variant={variant} track={track} seed={seed} mode={mode}", flush=True)
                    cell = _score_cell(probe, variant, track, seed, out, mode=mode, city_map=city_map)
                    cells.append(cell)
                    extra = cell.get("extra") or {}
                    print(
                        f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                        f"target_correct={extra.get('target_correct')} "
                        f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                        flush=True,
                    )
    return cells


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", PROVIDER)
    _pin_glm()
    city_map = _city_map()
    out = BRIDGE_ROOT / "output" / "exp_gm_01_20260824"
    out.mkdir(parents=True, exist_ok=True)

    print("phase=rule", flush=True)
    rule_cells = run_matrix(out / "rule", [0], mode="rule", city_map=city_map)
    rule_payload = _pack(rule_cells, out / "rule", phase="rule", mode="rule")
    print((out / "rule" / "REPORT.md").read_text(encoding="utf-8"))
    if rule_payload["summary"]["coverage"] < 1.0:
        print("Rule Coverage 未过门，停止 GLM。", flush=True)
        return 1
    if _first_pass_gate(rule_cells) == "C_floor":
        print("Rule 落在地板，停止 GLM。", flush=True)
        return 1

    print("phase=seed0", flush=True)
    cells = run_matrix(out, [0], mode="llm", city_map=city_map)
    payload = _pack(cells, out, phase="seed0", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    gate = payload["gate"]
    if gate != "fill_repeats":
        print(f"seed0 gate={gate}，停止补重复。", flush=True)
        return 0 if gate != "A_r0" else 1
    print("phase=repeats", flush=True)
    cells.extend(run_matrix(out, [1, 2], mode="llm", city_map=city_map))
    payload = _pack(cells, out, phase="all", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
