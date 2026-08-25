#!/usr/bin/env python3
"""EXP-GM-L1-01. Full Multi interruption recovery. Direct is solvability only."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from exp_gm_l1_01.budget import KINDS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_l1_01.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_l1_01.loop import run_cell, run_direct
from exp_gm_l1_01.prompts import rule_checkpoint, rule_direct, rule_handoff, rule_resume, rule_step
from exp_gm_l1_01.rule_tests import main as rule_main
from exp_gm_l1_01.scorer import score_cell
from exp_gm_l1_01.loader import solve_outputs
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_l1_01_handoff"
EXPERIMENT_ID = "EXP-GM-L1-01"
OUT = BRIDGE_ROOT / "output" / "exp_gm_l1_01_20260825"


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault(PROVIDER, {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 2048)
        glm["temperature"] = TEMPERATURE
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = PROVIDER
    tasks = dict(routing.get("tasks") or {})
    tasks["interview"] = PROVIDER
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = PROVIDER
    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    apply_eval_mode_runtime(CONFIG)


def _llm(prompt: str) -> str:
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _load_freeze() -> dict:
    path = OUT / "FREEZE.yaml"
    if path.is_file():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    from exp_gm_l1_01.freeze import write_manifest

    return write_manifest(OUT)


def _valid(cells: list[dict], track: str | None = None, variant: str | None = None) -> list[dict]:
    out = []
    for cell in cells:
        extra = cell.get("extra") or {}
        if track is not None and extra.get("track") != track:
            continue
        if variant is not None and extra.get("variant") != variant:
            continue
        if cell.get("measurement_valid"):
            out.append(cell)
    return out


def _mean(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    vals = []
    for cell in cells:
        extra = cell.get("extra") or {}
        value = extra.get(field)
        if value is None:
            continue
        vals.append(float(value) if not isinstance(value, bool) else float(value))
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _rate(cells: list[dict], field: str) -> float | None:
    if not cells:
        return None
    return round(sum(int(bool((c.get("extra") or {}).get(field))) for c in cells) / len(cells), 4)


def _full_rate(cells: list[dict], track: str) -> float | None:
    subset = [c for c in _valid(cells, track) if c.get("full_pass") is not None]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _coverage_track(cells: list[dict], track: str) -> float:
    subset = [c for c in cells if (c.get("extra") or {}).get("track") == track]
    if not subset:
        return 0.0
    return round(sum(int(bool(c.get("measurement_valid"))) for c in subset) / len(subset), 4)


def _strict_pair(cells: list[dict], track: str) -> float | None:
    groups: dict[tuple, dict[str, dict]] = {}
    for cell in _valid(cells, track):
        extra = cell.get("extra") or {}
        key = (extra.get("task_id"), extra.get("repeat_id"), extra.get("track"))
        groups.setdefault(key, {})[str(extra.get("variant"))] = cell
    pairs = [g for g in groups.values() if "control" in g and "intervention" in g]
    if not pairs:
        return None
    n = sum(1 for g in pairs if g["control"].get("full_pass") == 1 and g["intervention"].get("full_pass") == 1)
    return round(n / len(pairs), 4)


def _isolation_ok(cells: list[dict]) -> bool:
    ckpts = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_checkpoint"]
    hands = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_handoff"]
    if not ckpts or not hands:
        return False
    for cell in ckpts:
        extra = cell.get("extra") or {}
        if extra.get("variant") == "intervention" and extra.get("checkpoint_delivered"):
            return False
        if extra.get("variant") == "intervention" and not extra.get("b_ran"):
            return False
        if not extra.get("drop_checkpoint_isolated", True):
            return False
    for cell in hands:
        extra = cell.get("extra") or {}
        if extra.get("variant") == "intervention" and extra.get("handoff_completed"):
            return False
        if not extra.get("drop_handoff_isolated", True):
            return False
    return True


def _budget_ok(cells: list[dict]) -> bool:
    return bool(cells) and all((c.get("extra") or {}).get("budget_calls") == len(KINDS) for c in cells)


def _seed0_gate(cells: list[dict], coverage: float) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _budget_ok(cells) or not _isolation_ok(cells):
        return "A_r0"
    multi = _full_rate(cells, "multi")
    if multi == 0.0:
        return "C_floor"
    drop_c = _full_rate(cells, "drop_checkpoint")
    drop_h = _full_rate(cells, "drop_handoff")
    if multi == 1.0 and drop_c == 1.0 and drop_h == 1.0:
        return "C_ceiling"
    return "off_floor"


def _interpret(gate: str, *, direct_ok: bool, full: dict[str, float | None]) -> str:
    if not direct_ok:
        return "Direct 不可做。停止。Direct 不是正式系统结果。不解释 Multi，不能说中断恢复失败。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0。不解释能力。"
    if gate == "C_floor":
        return "Full Multi 处于地板。不能估计中断恢复与角色接替的多智能体价值。不能说 L1 已经通过。"
    if gate == "C_ceiling":
        return "三轨都高：Drop 无效或任务不依赖检查点/接替交付。不补 54 格。"
    multi = full.get("multi")
    if multi == 1.0:
        return "R0 有效且 Full Multi 通过。仍是开发集 seed0，不能扩写成一般性长期连续性已通过。"
    return "R0 有效且 Full Multi 不在地板。按首错定位检查点、接替与恢复位置。不能提前说 L1 已经通过。"


def _metrics(cells: list[dict]) -> dict:
    full = {track: _full_rate(cells, track) for track in TRACKS}
    inter_multi = _valid(cells, "multi", "intervention")
    payload = {
        "Coverage": {track: _coverage_track(cells, track) for track in TRACKS},
        "CheckpointCreated": {track: _rate(_valid(cells, track), "checkpoint_created") for track in TRACKS},
        "CheckpointDelivered": {track: _rate(_valid(cells, track, "intervention"), "checkpoint_delivered") for track in TRACKS},
        "ResumePositionCorrect": {track: _rate(_valid(cells, track), "resume_position_correct") for track in TRACKS},
        "CompletedWorkPreserved": {track: _rate(_valid(cells, track), "completed_work_preserved") for track in TRACKS},
        "DuplicateActionRate": {track: _mean(_valid(cells, track), "duplicate_action_rate") for track in TRACKS},
        "HandoffCompleted": {track: _rate(_valid(cells, track), "handoff_completed") for track in TRACKS},
        "WorkflowComplete": {track: _rate(_valid(cells, track), "workflow_complete") for track in TRACKS},
        "RecoveryLatency": _mean(inter_multi, "recovery_latency"),
        "FullPass": full,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "floor": full["multi"] == 0.0,
        "ceiling": full["multi"] == 1.0 and full["drop_checkpoint"] == 1.0 and full["drop_handoff"] == 1.0,
    }
    return payload


def _claim(gate: str, interpretation: str, *, direct_ok: bool) -> str:
    if not direct_ok:
        return "Direct 不可做。停止。不跑 Multi。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0。不解释能力。"
    if gate == "C_floor":
        return "Full Multi 共地板。不能估计多智能体价值。不能说 L1 已通过。"
    if gate == "C_ceiling":
        return "三轨都高：Drop 无效或任务不依赖交付。不补 54 格。"
    return interpretation


def _pack(
    cells: list[dict],
    out: Path,
    *,
    phase: str,
    gate: str,
    freeze: dict,
    direct_ok: bool,
    direct_fullpass: float | None,
) -> None:
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"] if cells else None
    metrics = _metrics(cells) if cells else {}
    interpretation = _interpret(gate, direct_ok=direct_ok, full=(metrics.get("FullPass") or {}))
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "parent": "C1_STAGE",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "holdout_allowed": False,
        "direct_ok": direct_ok,
        "direct_fullpass": direct_fullpass,
        "direct_is_formal_result": False,
        "primary_track": "multi",
        "coverage": coverage,
        "repeat_1_2_allowed": gate == "off_floor",
        "c1_status": "development_partial_pass",
        "does_not_overwrite": ["EXP-GM-C1-01", "EXP-GM-C1-02", "EXP-GM-C1-03"],
        "claim": _claim(gate, interpretation, direct_ok=direct_ok),
        "interpretation": interpretation,
        "metrics": metrics,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "freeze": freeze.get("base_commit"),
        "do_not": ["run_c1_04", "tune_c1_prompts", "create_c1_holdout"],
    }
    (out / "GATE.yaml").write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    m = metrics
    full = m.get("FullPass") or {}
    lines = [
        f"# {EXPERIMENT_ID}",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- 正式对象：Full Multi。Direct 非正式结果。不覆盖 C1。",
        "- ranking_eligible：false",
        f"- Direct 可做：{direct_ok}（FullPass={direct_fullpass}，仅校准）",
        f"- 冻结：{freeze.get('base_commit')}",
        f"- Coverage：{coverage}",
        "",
        "| 指标 | Multi | DropCheckpoint | DropHandoff |",
        "|---|---:|---:|---:|",
        f"| Coverage | {(m.get('Coverage') or {}).get('multi')} | {(m.get('Coverage') or {}).get('drop_checkpoint')} | {(m.get('Coverage') or {}).get('drop_handoff')} |",
        f"| CheckpointCreated | {(m.get('CheckpointCreated') or {}).get('multi')} | {(m.get('CheckpointCreated') or {}).get('drop_checkpoint')} | {(m.get('CheckpointCreated') or {}).get('drop_handoff')} |",
        f"| ResumePositionCorrect | {(m.get('ResumePositionCorrect') or {}).get('multi')} | {(m.get('ResumePositionCorrect') or {}).get('drop_checkpoint')} | {(m.get('ResumePositionCorrect') or {}).get('drop_handoff')} |",
        f"| HandoffCompleted | {(m.get('HandoffCompleted') or {}).get('multi')} | {(m.get('HandoffCompleted') or {}).get('drop_checkpoint')} | {(m.get('HandoffCompleted') or {}).get('drop_handoff')} |",
        f"| WorkflowComplete | {(m.get('WorkflowComplete') or {}).get('multi')} | {(m.get('WorkflowComplete') or {}).get('drop_checkpoint')} | {(m.get('WorkflowComplete') or {}).get('drop_handoff')} |",
        f"| FullPass | {full.get('multi')} | {full.get('drop_checkpoint')} | {full.get('drop_handoff')} |",
        f"| StrictPair | {(m.get('StrictPair') or {}).get('multi')} | {(m.get('StrictPair') or {}).get('drop_checkpoint')} | {(m.get('StrictPair') or {}).get('drop_handoff')} |",
        "",
        f"- RecoveryLatency（intervention multi）：{m.get('RecoveryLatency')}",
        f"- first_error：{m.get('first_error')}",
        f"- 解释：{interpretation}",
        "",
        f"**结论：** {_claim(gate, interpretation, direct_ok=direct_ok)} 功能进度：Direct 未过或 seed0 测量无效则仍约 75%；seed0 Coverage=1.0 后约 85%。不做 C1-04。",
        "",
    ]
    if cells:
        lines += ["| instance | valid | FullPass | track | first_error |", "|---|---|---|---|---|"]
        for cell in cells:
            extra = cell.get("extra") or {}
            err = (cell.get("process_profile") or {}).get("first_error")
            lines.append(
                f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | {extra.get('track')} | {err} |"
            )
        lines.append("")
    (out / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "cell_table.json").write_text(json.dumps({"cells": cells, "gate": payload}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _score_and_store(*, task, variant, track, repeat_id, loop, out_dir) -> dict:
    instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
    cell = score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=repeat_id,
        loop=loop,
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
    )
    run_dir = out_dir / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    extra = cell.get("extra") or {}
    print(
        f"done {instance_id} valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} first_error={extra.get('first_error')}",
        flush=True,
    )
    return cell


def _fns(task: dict, variant: str, mode: str):
    successor = "worker_b" if variant == "intervention" else "worker_a"

    def step1(_p):
        if mode != "rule":
            return _llm(_p)
        return json.dumps(rule_step(task, "worker_a", task["step_ids"][0]), ensure_ascii=False)

    def checkpoint(_p):
        if mode != "rule":
            return _llm(_p)
        first = task["step_ids"][0]
        return json.dumps(rule_checkpoint(task, "worker_a", [first], {first: solve_outputs(task)[first]}), ensure_ascii=False)

    def handoff(_p):
        if mode != "rule":
            return _llm(_p)
        return json.dumps(rule_handoff(task, variant, {"completed_steps": [task["step_ids"][0]]}), ensure_ascii=False)

    def resume(_p):
        if mode != "rule":
            return _llm(_p)
        ck = {"checkpoint_version": "ckpt-001", "completed_steps": [task["step_ids"][0]]}
        ho = {"successor": successor, "checkpoint_version": "ckpt-001", "resume_step": task["step_ids"][1]}
        return json.dumps(rule_resume(task, successor, ck, ho), ensure_ascii=False)

    def step2(_p):
        if mode != "rule":
            return _llm(_p)
        prior = {task["step_ids"][0]: solve_outputs(task)[task["step_ids"][0]]}
        return json.dumps(rule_step(task, successor, task["step_ids"][1], prior), ensure_ascii=False)

    def step3(_p):
        if mode != "rule":
            return _llm(_p)
        outputs = solve_outputs(task)
        prior = {task["step_ids"][0]: outputs[task["step_ids"][0]], task["step_ids"][1]: outputs[task["step_ids"][1]]}
        return json.dumps(rule_step(task, successor, task["step_ids"][2], prior), ensure_ascii=False)

    return step1, checkpoint, handoff, resume, step2, step3


def run_direct_cells(out: Path, *, mode: str) -> list[dict]:
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            instance_id = f"{task['id']}_{variant}_direct_r0"
            print(f"run {instance_id} mode={mode}", flush=True)
            generate = (lambda _p, t=task, v=variant: json.dumps(rule_direct(t, v), ensure_ascii=False)) if mode == "rule" else _llm
            loop = run_direct(task=task, variant=variant, out_dir=out / "runs" / instance_id, generate_fn=generate)
            cells.append(_score_and_store(task=task, variant=variant, track="direct", repeat_id=0, loop=loop, out_dir=out))
    return cells


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                print(f"run {instance_id} mode={mode}", flush=True)
                step1, checkpoint, handoff, resume, step2, step3 = _fns(task, variant, mode)
                loop = run_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    out_dir=out / "runs" / instance_id,
                    step1_fn=step1,
                    checkpoint_fn=checkpoint,
                    handoff_fn=handoff,
                    resume_fn=resume,
                    step2_fn=step2,
                    step3_fn=step3,
                )
                cells.append(_score_and_store(task=task, variant=variant, track=track, repeat_id=repeat_id, loop=loop, out_dir=out))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "direct", "seed0"), default="seed0")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    from exp_gm_l1_01.fairness import preflight

    check = preflight()
    print("fairness_preflight", json.dumps({"ok": check["ok"], "n_leaks": len(check["leaks"])}, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed", check["leaks"], flush=True)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = _load_freeze()
    if args.phase == "rule":
        _pack([], OUT, phase="rule", gate="rule_pass", freeze=freeze, direct_ok=False, direct_fullpass=None)
        print("Rule 已过门并冻结。下一步 Direct 6 格。", flush=True)
        return 0
    print("phase=direct", flush=True)
    direct_cells = run_direct_cells(OUT, mode="llm")
    direct_full = _full_rate(direct_cells, "direct")
    direct_cov = summarize_workflow(WORKFLOW_ID, direct_cells)["coverage"]
    direct_ok = direct_cov == 1.0 and len(direct_cells) == 6 and direct_full == 1.0
    (OUT / "direct_cells.json").write_text(
        json.dumps({"ok": direct_ok, "fullpass": direct_full, "coverage": direct_cov, "cells": direct_cells}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"direct_ok={direct_ok} direct_fullpass={direct_full} coverage={direct_cov} (not formal)", flush=True)
    if not direct_ok:
        _pack(direct_cells, OUT, phase="direct", gate="direct_fail", freeze=freeze, direct_ok=False, direct_fullpass=direct_full)
        print("Direct 未过。停止。不跑 Multi。不能说中断恢复失败，只能说新题 Direct 不可做。", flush=True)
        return 1
    if args.phase == "direct":
        _pack(direct_cells, OUT, phase="direct", gate="direct_pass", freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
        print("Direct 已过。seed0 用 --phase seed0。", flush=True)
        return 0
    print("phase=seed0", flush=True)
    cells = run_repeat(OUT, 0, mode="llm")
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    gate = _seed0_gate(cells, coverage)
    _pack(cells, OUT, phase="seed0", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    print((OUT / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。不补 repeat 1/2。", flush=True)
        return 1
    if gate == "C_floor":
        print("gate=C_floor。seed0 测量有效但 Full Multi 在地板。不补 54 格。", flush=True)
        return 0
    print(f"gate={gate}。seed0 完成。不自动补 repeat 1/2。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
