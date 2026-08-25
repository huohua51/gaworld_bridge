#!/usr/bin/env python3
"""EXP-GM-02: T2 household care. Rule first, seed 0, fill repeats only if identifiable."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_02.loop import run_cell_loop
from exp_gm_02.probes import PROBES
from exp_gm_02.roles import agent_prompt, parse_json_object, rule_agent
from exp_gm_02.scoring import (
    care_adaptation_rate,
    control_stability_rate,
    score_cell,
    unnecessary_replan_rate,
)
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_02_household_care"
TRACKS = ("direct_household_state", "full_family_event", "drop_family_event")
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


def _rule_fn(probe: dict):
    def agent(notice, _schedule):
        return rule_agent(probe, notice=notice)

    return agent


def _llm_fn(probe: dict):
    def agent(notice, schedule):
        extra = "没有收到家庭照料事件。必须输出完整占位字段，不要主动认领照料。" if notice is None else ""
        text = _llm(agent_prompt(probe, notice=notice, schedule=schedule, extra=extra))
        try:
            return parse_json_object(text)
        except (ValueError, json.JSONDecodeError):
            return {}

    return agent


def _score_cell(probe: dict, variant: str, track: str, seed: int, out_root: Path, *, mode: str) -> dict:
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
    )
    cell = score_cell(
        probe=probe, variant=variant, track=track, seed=seed,
        loop=loop, workflow_id=WORKFLOW_ID, instance_id=instance_id,
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
        and c.get("measurement_valid")
    ]
    if not subset:
        return None
    if field == "target_correct":
        return round(sum(int(bool((c.get("extra") or {}).get("target_correct"))) for c in subset) / len(subset), 4)
    scored = [c for c in subset if c.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(c["full_pass"]) for c in scored) / len(scored), 4)


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
        "direct_household_state": _rate(cells, "direct_household_state", "full_pass"),
        "full_family_event": _rate(cells, "full_family_event", "full_pass"),
        "drop_family_event": _rate(cells, "drop_family_event", "full_pass"),
        "direct_target": _rate(cells, "direct_household_state", "target_correct"),
        "full_target": _rate(cells, "full_family_event", "target_correct"),
        "drop_target": _rate(cells, "drop_family_event", "target_correct"),
        "full_control": _rate(cells, "full_family_event", "full_pass", "control"),
        "full_intervention": _rate(cells, "full_family_event", "full_pass", "intervention"),
        "drop_control": _rate(cells, "drop_family_event", "full_pass", "control"),
        "drop_intervention": _rate(cells, "drop_family_event", "full_pass", "intervention"),
    }
    diagnostics = {
        "care_adaptation_rate": {
            "direct_household_state": care_adaptation_rate(cells, "direct_household_state"),
            "full_family_event": care_adaptation_rate(cells, "full_family_event"),
            "drop_family_event": care_adaptation_rate(cells, "drop_family_event"),
        },
        "control_stability_rate": {
            "direct_household_state": control_stability_rate(cells, "direct_household_state"),
            "full_family_event": control_stability_rate(cells, "full_family_event"),
            "drop_family_event": control_stability_rate(cells, "drop_family_event"),
        },
        "unnecessary_replan_rate": {
            "direct_household_state": unnecessary_replan_rate(cells, "direct_household_state"),
            "full_family_event": unnecessary_replan_rate(cells, "full_family_event"),
            "drop_family_event": unnecessary_replan_rate(cells, "drop_family_event"),
        },
    }
    event_value_full = None if rates["full_family_event"] is None or rates["drop_family_event"] is None else round(
        rates["full_family_event"] - rates["drop_family_event"], 4
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-02",
        "task_id": "TASK-L2-household-care",
        "phase": phase,
        "mode": mode,
        "ranking_eligible": False,
        "gate": (
            "completed_repeats" if phase == "all"
            else _first_pass_gate(cells) if phase.startswith("seed0") or phase == "rule"
            else None
        ),
        "summary": summary,
        "coverage": {track: _coverage(cells, track) for track in TRACKS},
        "rates": rates,
        "diagnostics": diagnostics,
        "event_value_full": event_value_full,
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# EXP-GM-02 T2 household care",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；mode：{mode}",
        "- ranking_eligible：false",
        "- 动作接口：扁平 submit_care_action，control 必须填完整 NONE 占位",
        "",
        "## 覆盖与主结果",
        "",
        f"- requested：{summary['requested']}",
        f"- measurement_valid：{summary['measurement_valid']}",
        f"- coverage：{summary['coverage']}",
        f"- gate：{payload['gate']}",
        f"- FullPass direct / full / drop：{rates['direct_household_state']} / {rates['full_family_event']} / {rates['drop_family_event']}",
        f"- TargetCorrect direct / full / drop：{rates['direct_target']} / {rates['full_target']} / {rates['drop_target']}",
        f"- EventValue_full (Full − Drop)：{event_value_full}",
        "",
        "## 分变体诊断",
        "",
        f"- CareAdaptationRate direct / full / drop：{diagnostics['care_adaptation_rate']['direct_household_state']} / {diagnostics['care_adaptation_rate']['full_family_event']} / {diagnostics['care_adaptation_rate']['drop_family_event']}",
        f"- ControlStabilityRate direct / full / drop：{diagnostics['control_stability_rate']['direct_household_state']} / {diagnostics['control_stability_rate']['full_family_event']} / {diagnostics['control_stability_rate']['drop_family_event']}",
        f"- UnnecessaryReplanRate direct / full / drop：{diagnostics['unnecessary_replan_rate']['direct_household_state']} / {diagnostics['unnecessary_replan_rate']['full_family_event']} / {diagnostics['unnecessary_replan_rate']['drop_family_event']}",
        "",
        "重点：没有家庭事件时，模型会不会像 GM-01 一样为了表现适应性而主动制造变化。",
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


def run_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for probe in PROBES:
        for variant in VARIANTS:
            for track in TRACKS:
                for seed in seeds:
                    print(f"run {probe['id']} variant={variant} track={track} seed={seed} mode={mode}", flush=True)
                    cell = _score_cell(probe, variant, track, seed, out, mode=mode)
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
    out = BRIDGE_ROOT / "output" / "exp_gm_02_20260824"
    out.mkdir(parents=True, exist_ok=True)

    print("phase=rule", flush=True)
    rule_cells = run_matrix(out / "rule", [0], mode="rule")
    rule_payload = _pack(rule_cells, out / "rule", phase="rule", mode="rule")
    print((out / "rule" / "REPORT.md").read_text(encoding="utf-8"))
    if rule_payload["summary"]["coverage"] < 1.0 or _first_pass_gate(rule_cells) == "C_floor":
        print("Rule 未过门，停止 GLM。", flush=True)
        return 1

    print("phase=seed0", flush=True)
    cells = run_matrix(out, [0], mode="llm")
    payload = _pack(cells, out, phase="seed0", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    gate = payload["gate"]
    if gate != "fill_repeats":
        print(f"seed0 gate={gate}，停止补重复。", flush=True)
        return 0 if gate != "A_r0" else 1
    print("phase=repeats", flush=True)
    cells.extend(run_matrix(out, [1, 2], mode="llm"))
    payload = _pack(cells, out, phase="all", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
