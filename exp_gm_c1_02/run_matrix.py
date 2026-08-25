#!/usr/bin/env python3
"""EXP-GM-C1-02. Multi is the primary system. Direct is solvability only."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_c1_02.budget import KINDS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_c1_02.freeze import write_manifest
from exp_gm_c1_02.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_c1_02.loop import run_cell, run_direct
from exp_gm_c1_02.prompts import rule_commit, rule_direct, rule_plan_from_reports, rule_report, rule_revision
from exp_gm_c1_02.rule_tests import main as rule_main
from exp_gm_c1_02.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_c1_02_coordination"
EXPERIMENT_ID = "EXP-GM-C1-02"


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


def _budget_ok(cells: list[dict], *, kinds: tuple[str, ...] = KINDS) -> bool:
    return bool(cells) and all((c.get("extra") or {}).get("budget_calls") == len(kinds) for c in cells)


def _isolation_ok(cells: list[dict]) -> bool:
    revs = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_revision"]
    coords = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_coordinator"]
    if not revs or not coords:
        return False
    for cell in revs:
        extra = cell.get("extra") or {}
        if extra.get("variant") == "intervention" and extra.get("revision_delivered"):
            return False
        if not extra.get("b_ran"):
            return False
    for cell in coords:
        extra = cell.get("extra") or {}
        if extra.get("plan_delivered"):
            return False
    return True


def _seed0_gate(cells: list[dict], coverage: float) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _budget_ok(cells) or not _isolation_ok(cells):
        return "A_r0"
    multi = _full_rate(cells, "multi")
    if multi == 0.0:
        return "C_floor"
    if multi == 1.0 and _full_rate(cells, "drop_revision") == 1.0 and _full_rate(cells, "drop_coordinator") == 1.0:
        return "C_ceiling"
    return "off_floor"


def _interpret(full: dict[str, float | None]) -> str:
    multi, drop_r, drop_c = full.get("multi"), full.get("drop_revision"), full.get("drop_coordinator")
    if multi is None:
        return "Coverage 不足，不解释。"
    if multi == 0.0:
        return "Full Multi 处于地板。不能估计多智能体协调价值。不能说集体协调已通过。"
    if multi == 1.0 and drop_r == 1.0 and drop_c == 1.0:
        return "三轨都高：Drop 无效或任务不依赖方案交付。不补 54 格。"
    if multi == 1.0 and drop_r is not None and drop_r < 1.0:
        return "Full Multi 可通过；丢掉 B 的动态约束修订后下降。这只能作为本开发集上的系统结果，不能宣称泛化。"
    return "Full Multi 未处于地板。按首错定位方案形成、交付或执行。不能提前说集体协调已经通过。"


def _metrics(cells: list[dict]) -> dict:
    full = {track: _full_rate(cells, track) for track in TRACKS}
    return {
        "Coverage": {track: _coverage_track(cells, track) for track in TRACKS},
        "ActualFinalConflictFree": {track: _mean(_valid(cells, track), "actual_final_conflict_free") for track in TRACKS},
        "JointConstraintSatisfaction": {track: _mean(_valid(cells, track), "joint_constraint_satisfaction") for track in TRACKS},
        "JointPlanCommitted": {track: _mean(_valid(cells, track), "joint_plan_committed") for track in TRACKS},
        "ExecutionMatchesPlan": {track: _mean(_valid(cells, track), "execution_matches_plan") for track in TRACKS},
        "RoleCompletion": {track: _mean(_valid(cells, track), "role_completion") for track in TRACKS},
        "ConflictRepairSuccess": {track: _mean(_valid(cells, track), "conflict_repair_success") for track in TRACKS},
        "FullPass": full,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "interpretation": _interpret(full),
        "floor": full["multi"] == 0.0,
        "ceiling": full["multi"] == 1.0 and full["drop_revision"] == 1.0 and full["drop_coordinator"] == 1.0,
    }


def _claim(gate: str, metrics: dict, *, direct_ok: bool) -> str:
    if not direct_ok:
        return "Direct 不可做。停止。Direct 不是正式系统结果。不解释 Multi。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0。不解释能力。不补重复。"
    if gate == "C_floor":
        return "Full Multi 共地板。不能估计多智能体价值。不补 54 格。不能说集体协调已通过。"
    if gate == "C_ceiling":
        return "三轨都高：Drop 无效或任务不依赖交付。不补 54 格。"
    return f"{metrics.get('interpretation')} 组件修复通过不等于集体协调通过。"


def _pack(cells: list[dict], out: Path, *, phase: str, gate: str | None, freeze: dict | None, direct_ok: bool, direct_fullpass: float | None) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "parent": "CAL-GM-C1-REPAIR-01",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "generalization_claim": False,
        "direct_ok": direct_ok,
        "direct_fullpass": direct_fullpass,
        "direct_is_formal_result": False,
        "primary_track": "multi",
        "claim": _claim(gate or "", metrics, direct_ok=direct_ok),
        "freeze": freeze,
        "summary": summary,
        "metrics": metrics,
        "model": MODEL,
        "temperature": TEMPERATURE,
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    m = metrics
    lines = [
        "# EXP-GM-C1-02",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- 正式对象：Full Multi。Direct 非正式结果。",
        "- ranking_eligible：false；不能说集体协调已经通过，除非 Full Multi 过门且按指标拆开报告。",
        f"- Direct 可做：{direct_ok}（FullPass={direct_fullpass}，仅校准）",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        "| 指标 | Multi | DropRevision | DropCoordinator |",
        "|---|---:|---:|---:|",
        f"| Coverage | {m['Coverage']['multi']} | {m['Coverage']['drop_revision']} | {m['Coverage']['drop_coordinator']} |",
        f"| ActualFinalConflictFree | {m['ActualFinalConflictFree']['multi']} | {m['ActualFinalConflictFree']['drop_revision']} | {m['ActualFinalConflictFree']['drop_coordinator']} |",
        f"| JointConstraintSatisfaction | {m['JointConstraintSatisfaction']['multi']} | {m['JointConstraintSatisfaction']['drop_revision']} | {m['JointConstraintSatisfaction']['drop_coordinator']} |",
        f"| JointPlanCommitted | {m['JointPlanCommitted']['multi']} | {m['JointPlanCommitted']['drop_revision']} | {m['JointPlanCommitted']['drop_coordinator']} |",
        f"| ExecutionMatchesPlan | {m['ExecutionMatchesPlan']['multi']} | {m['ExecutionMatchesPlan']['drop_revision']} | {m['ExecutionMatchesPlan']['drop_coordinator']} |",
        f"| RoleCompletion | {m['RoleCompletion']['multi']} | {m['RoleCompletion']['drop_revision']} | {m['RoleCompletion']['drop_coordinator']} |",
        f"| ConflictRepairSuccess | {m['ConflictRepairSuccess']['multi']} | {m['ConflictRepairSuccess']['drop_revision']} | {m['ConflictRepairSuccess']['drop_coordinator']} |",
        f"| FullPass | {m['FullPass']['multi']} | {m['FullPass']['drop_revision']} | {m['FullPass']['drop_coordinator']} |",
        f"| StrictPair | {m['StrictPair']['multi']} | {m['StrictPair']['drop_revision']} | {m['StrictPair']['drop_coordinator']} |",
        "",
        f"- first_error：{m['first_error']}",
        f"- 解释：{m['interpretation']}",
        "",
        f"**结论：** {payload['claim']}",
        "",
        "| instance | valid | FullPass | track | first_error |",
        "|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('track')} | {(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "REPORT_seed0.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import yaml

    (out / "GATE.yaml").write_text(
        yaml.safe_dump(
            {
                "experiment_id": EXPERIMENT_ID,
                "phase": phase,
                "gate": gate,
                "direct_ok": direct_ok,
                "direct_fullpass": direct_fullpass,
                "direct_is_formal_result": False,
                "primary_track": "multi",
                "multi_fullpass": m["FullPass"]["multi"],
                "drop_revision_fullpass": m["FullPass"]["drop_revision"],
                "drop_coordinator_fullpass": m["FullPass"]["drop_coordinator"],
                "interpretation": m["interpretation"],
                "repeat_1_2": "not_run" if phase != "all" else "complete",
                "holdout": "not_created",
                "claim": payload["claim"],
                "ranking_eligible": False,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return payload


def _score_and_store(*, task, variant, track, repeat_id, loop, out_dir: Path, mode: str) -> dict:
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
    extra = dict(cell.get("extra") or {})
    extra["mode"] = mode
    extra["model_version"] = "rule" if mode == "rule" else MODEL
    cell["extra"] = extra
    cell["ranking_eligible"] = False
    parent = Path(loop["world_path"]).parent if loop.get("world_path") else out_dir / "runs" / instance_id
    parent.mkdir(parents=True, exist_ok=True)
    (parent / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
        f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
        flush=True,
    )
    return cell


def _fns(task, variant, track, mode: str):
    def report_a(prompt):
        return json.dumps(rule_report(task, "agent_a", baseline=True), ensure_ascii=False) if mode == "rule" else _llm(prompt)

    def report_b(prompt):
        return json.dumps(rule_report(task, "agent_b", baseline=True), ensure_ascii=False) if mode == "rule" else _llm(prompt)

    def initial_fn(prompt):
        if mode != "rule":
            return _llm(prompt)
        marker = "【已送达初始报告】"
        reports = json.loads(prompt.split(marker, 1)[1].split("\n", 1)[0].strip()) if marker in prompt else {}
        return json.dumps(rule_plan_from_reports(task, reports, version="plan-init"), ensure_ascii=False)

    def revision_fn(prompt):
        return json.dumps(rule_revision(task, variant), ensure_ascii=False) if mode == "rule" else _llm(prompt)

    def propose_fn(prompt):
        if mode != "rule":
            return _llm(prompt)
        marker = "【最新已送达约束】"
        latest = json.loads(prompt.split(marker, 1)[1].split("\n", 1)[0].strip()) if marker in prompt else {}
        return json.dumps(rule_plan_from_reports(task, latest, version="plan-001"), ensure_ascii=False)

    def commit_a(prompt):
        if mode != "rule":
            return _llm(prompt)
        plan = json.loads(prompt.split("【联合方案】", 1)[1].strip()) if "【联合方案】" in prompt else None
        return json.dumps(rule_commit(task, "agent_a", variant, plan), ensure_ascii=False)

    def commit_b(prompt):
        if mode != "rule":
            return _llm(prompt)
        plan = json.loads(prompt.split("【联合方案】", 1)[1].strip()) if "【联合方案】" in prompt else None
        return json.dumps(rule_commit(task, "agent_b", variant, plan), ensure_ascii=False)

    return report_a, report_b, initial_fn, revision_fn, propose_fn, commit_a, commit_b


def run_direct_cells(out: Path, *, mode: str) -> list[dict]:
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            instance_id = f"{task['id']}_{variant}_direct_r0"
            print(f"run {instance_id} mode={mode}", flush=True)
            generate_fn = (lambda _p, t=task, v=variant: json.dumps(rule_direct(t, v), ensure_ascii=False)) if mode == "rule" else _llm
            loop = run_direct(task=task, variant=variant, out_dir=out / "runs" / instance_id, generate_fn=generate_fn)
            cells.append(_score_and_store(task=task, variant=variant, track="direct", repeat_id=0, loop=loop, out_dir=out, mode=mode))
    return cells


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                print(f"run {instance_id} mode={mode}", flush=True)
                report_a, report_b, initial_fn, revision_fn, propose_fn, commit_a, commit_b = _fns(task, variant, track, mode)
                loop = run_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    out_dir=out / "runs" / instance_id,
                    report_a_fn=report_a,
                    report_b_fn=report_b,
                    initial_fn=initial_fn,
                    revision_fn=revision_fn,
                    propose_fn=propose_fn,
                    commit_a_fn=commit_a,
                    commit_b_fn=commit_b,
                )
                cells.append(_score_and_store(task=task, variant=variant, track=track, repeat_id=repeat_id, loop=loop, out_dir=out, mode=mode))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "direct", "seed0", "repeats", "all"), default="seed0")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    if args.phase == "rule":
        print("Rule 已过门。", flush=True)
        return 0
    from exp_gm_c1_02.fairness import preflight

    out = BRIDGE_ROOT / "output" / "exp_gm_c1_02_20260825"
    out.mkdir(parents=True, exist_ok=True)
    check = preflight()
    print("fairness_preflight", json.dumps({"ok": check["ok"], "n_leaks": len(check["leaks"])}, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed", check["leaks"], flush=True)
        return 1
    if args.phase == "repeats":
        import yaml

        gate_doc = yaml.safe_load((out / "GATE.yaml").read_text(encoding="utf-8")) if (out / "GATE.yaml").is_file() else {}
        freeze = yaml.safe_load((out / "FREEZE.yaml").read_text(encoding="utf-8")) if (out / "FREEZE.yaml").is_file() else {}
        if not gate_doc.get("direct_ok"):
            print("repeats 需要 Direct 已过。", flush=True)
            return 1
        if gate_doc.get("gate") not in {"off_floor"}:
            print(f"repeats 拒绝：seed0 gate={gate_doc.get('gate')}。", flush=True)
            return 1
        prior = json.loads((out / "cell_table.json").read_text(encoding="utf-8"))
        cells = list((prior.get("summary") or {}).get("cells") or [])
        if len(cells) < 18:
            print("repeats 需要 seed0 的 18 格。", flush=True)
            return 1
        print("phase=repeats", flush=True)
        cells.extend(run_repeat(out, 1, mode="llm"))
        cells.extend(run_repeat(out, 2, mode="llm"))
        _pack(
            cells,
            out,
            phase="all",
            gate=str(gate_doc.get("gate")),
            freeze=freeze,
            direct_ok=True,
            direct_fullpass=gate_doc.get("direct_fullpass"),
        )
        print((out / "REPORT.md").read_text(encoding="utf-8"))
        return 0
    freeze = write_manifest(out)
    print("frozen", freeze.get("base_commit"), flush=True)
    print("phase=direct", flush=True)
    direct_cells = run_direct_cells(out, mode="llm")
    direct_full = _full_rate(direct_cells, "direct")
    direct_ok = summarize_workflow(WORKFLOW_ID, direct_cells)["coverage"] == 1.0 and len(direct_cells) == 6 and direct_full == 1.0
    (out / "direct_cells.json").write_text(json.dumps({"ok": direct_ok, "fullpass": direct_full, "cells": direct_cells}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"direct_ok={direct_ok} direct_fullpass={direct_full} (not formal)", flush=True)
    if not direct_ok:
        _pack(direct_cells, out, phase="direct", gate="direct_fail", freeze=freeze, direct_ok=False, direct_fullpass=direct_full)
        print("Direct 未过。停止。不跑 Multi。不能说集体协调失败，只能说新题 Direct 不可做。", flush=True)
        return 1
    if args.phase == "direct":
        print("Direct 已过。seed0 用 --phase seed0。", flush=True)
        return 0
    print("phase=seed0", flush=True)
    cells = run_repeat(out, 0, mode="llm")
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    gate = _seed0_gate(cells, coverage)
    _pack(cells, out, phase="seed0", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。不补 54 格。", flush=True)
        return 1
    if gate == "C_floor":
        print("Full Multi 地板。不补 54 格。不能说集体协调已通过。", flush=True)
        return 1
    if args.phase == "seed0":
        print(f"gate={gate}。seed0 完成。补 54 格用 --phase repeats。", flush=True)
        return 0
    print("phase=repeats", flush=True)
    cells.extend(run_repeat(out, 1, mode="llm"))
    cells.extend(run_repeat(out, 2, mode="llm"))
    _pack(cells, out, phase="all", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
