#!/usr/bin/env python3
"""EXP-GM-C1-01 collective coordination. Rule first; Direct; then seed0 18 cells only."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_c1_01.budget import KINDS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_c1_01.contract import parse_json_object
from exp_gm_c1_01.freeze import write_manifest
from exp_gm_c1_01.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_c1_01.loop import run_cell, run_direct
from exp_gm_c1_01.prompts import rule_commit, rule_direct, rule_plan, rule_report
from exp_gm_c1_01.rule_tests import main as rule_main
from exp_gm_c1_01.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_c1_01_coordination"


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
    return bool(cells) and all((c.get("extra") or {}).get("budget_calls") == len(kinds) for c in cells) and all(
        list((c.get("extra") or {}).get("budget_kinds") or []) == list(kinds) for c in cells
    )


def _isolation_ok(cells: list[dict]) -> bool:
    drops = [c for c in cells if (c.get("extra") or {}).get("track") == "drop"]
    if not drops:
        return False
    for cell in drops:
        extra = cell.get("extra") or {}
        if not extra.get("b_ran") or extra.get("b_delivered"):
            return False
    return True


def _seed0_gate(cells: list[dict], coverage: float) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _budget_ok(cells) or not _isolation_ok(cells):
        return "A_r0"
    single = _full_rate(cells, "single")
    multi = _full_rate(cells, "multi")
    drop = _full_rate(cells, "drop")
    if single == 0.0 and multi == 0.0:
        return "C_floor"
    if single == 1.0 and multi == 1.0 and drop == 1.0:
        return "C_ceiling"
    return "off_floor"


def _interpret(full: dict[str, float | None]) -> str:
    single, multi, drop = full.get("single"), full.get("multi"), full.get("drop")
    if single is None or multi is None or drop is None:
        return "Coverage 不足，不解释。"
    high = 1.0
    low = 0.5
    if single == 0.0 and multi == 0.0:
        return "共同能力地板，不能估计多 Agent 价值"
    if single == high and multi == high and drop == high:
        return "Drop 无效、任务存在泄漏或不依赖协调"
    if multi > single and drop is not None and drop < multi:
        return "分布式角色协调产生额外价值"
    if single >= high and multi >= high and drop <= low:
        return "通信有因果价值，尚无角色拆分优势"
    if multi >= high and drop < multi and (single is not None and single < multi):
        return "分布式角色协调产生额外价值"
    if multi is not None and single is not None and multi >= high and drop is not None and drop < multi:
        errors = ""
        return "通信有因果价值，尚无角色拆分优势" if single >= multi else "分布式角色协调产生额外价值"
    return "Multi 收到信息仍失败：定位冲突检测、方案形成、确认或执行环节"


def _metrics(cells: list[dict]) -> dict:
    full = {track: _full_rate(cells, track) for track in TRACKS}
    floor = full["single"] == 0.0 and full["multi"] == 0.0
    ceiling = full["single"] == 1.0 and full["multi"] == 1.0 and full["drop"] == 1.0
    return {
        "Coverage": {track: _coverage_track(cells, track) for track in TRACKS},
        "individual_constraint_satisfaction": {track: _mean(_valid(cells, track), "individual_constraint_satisfaction") for track in TRACKS},
        "no_resource_conflict": {track: _mean(_valid(cells, track), "no_resource_conflict") for track in TRACKS},
        "joint_plan_committed": {track: _mean(_valid(cells, track), "joint_plan_committed") for track in TRACKS},
        "execution_matches_plan": {track: _mean(_valid(cells, track), "execution_matches_plan") for track in TRACKS},
        "FullPass": full,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "interpretation": _interpret(full),
        "floor": floor,
        "ceiling": ceiling,
    }


def _claim(gate: str, metrics: dict, *, direct_ok: bool) -> str:
    if not direct_ok:
        return "Direct 不可做。停止。不解释 Single/Multi/Drop。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0，不解释能力。不补重复。"
    if gate == "C_floor":
        return "Single 与 Multi 共地板。不能估计多 Agent 价值。不补 54 格。"
    if gate == "C_ceiling":
        return "三轨都高：Drop 无效、任务存在泄漏或不依赖协调。不补 54 格。"
    return f"{metrics.get('interpretation')}。repeat 0 已过测量门。先不补 54 格，不建留出。"


def _pack(cells: list[dict], out: Path, *, phase: str, gate: str | None, freeze: dict | None, direct_ok: bool, direct_fullpass: float | None) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-C1-01",
        "parent": "EXP-GM-T3-03",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "generalization_claim": False,
        "direct_ok": direct_ok,
        "direct_fullpass": direct_fullpass,
        "claim": _claim(gate or "", metrics, direct_ok=direct_ok),
        "freeze": freeze,
        "summary": summary,
        "fairness": {
            "coverage": summary["coverage"],
            "budget_ok": _budget_ok(cells),
            "isolation_ok": _isolation_ok(cells),
            "single_full": _full_rate(cells, "single"),
            "multi_full": _full_rate(cells, "multi"),
            "drop_full": _full_rate(cells, "drop"),
        },
        "metrics": metrics,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "note": "集体协调试点。不补 T3，不建留出。第一轮只跑 18 格。",
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fair = payload["fairness"]
    m = metrics
    lines = [
        "# EXP-GM-C1-01",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- ranking_eligible：false",
        "- generalization_claim：false",
        f"- Direct 可做：{direct_ok}（FullPass={direct_fullpass}）",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        "## 测量门",
        "",
        f"- Coverage：{fair['coverage']}",
        f"- 预算均为 5 次：{fair['budget_ok']}",
        f"- Drop 发送者运行且接收者未收到：{fair['isolation_ok']}",
        "",
        "## 主报",
        "",
        "| 指标 | Single | Multi | Drop |",
        "|---|---:|---:|---:|",
        f"| Coverage | {m['Coverage']['single']} | {m['Coverage']['multi']} | {m['Coverage']['drop']} |",
        f"| individual_constraint_satisfaction | {m['individual_constraint_satisfaction']['single']} | {m['individual_constraint_satisfaction']['multi']} | {m['individual_constraint_satisfaction']['drop']} |",
        f"| no_resource_conflict | {m['no_resource_conflict']['single']} | {m['no_resource_conflict']['multi']} | {m['no_resource_conflict']['drop']} |",
        f"| joint_plan_committed | {m['joint_plan_committed']['single']} | {m['joint_plan_committed']['multi']} | {m['joint_plan_committed']['drop']} |",
        f"| execution_matches_plan | {m['execution_matches_plan']['single']} | {m['execution_matches_plan']['multi']} | {m['execution_matches_plan']['drop']} |",
        f"| FullPass | {m['FullPass']['single']} | {m['FullPass']['multi']} | {m['FullPass']['drop']} |",
        f"| StrictPair | {m['StrictPair']['single']} | {m['StrictPair']['multi']} | {m['StrictPair']['drop']} |",
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
        (out / "cell_table_seed0.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    import yaml

    (out / "GATE.yaml").write_text(
        yaml.safe_dump(
            {
                "experiment_id": "EXP-GM-C1-01",
                "phase": phase,
                "gate": gate,
                "direct_ok": direct_ok,
                "direct_fullpass": direct_fullpass,
                "coverage": fair["coverage"],
                "single_fullpass": fair["single_full"],
                "multi_fullpass": fair["multi_full"],
                "drop_fullpass": fair["drop_full"],
                "interpretation": m["interpretation"],
                "repeat_1_2": "not_run",
                "holdout": "not_created",
                "claim": payload["claim"],
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

                def report_a(prompt, t=task, v=variant):
                    if mode == "rule":
                        return json.dumps(rule_report(t, "agent_a", v), ensure_ascii=False)
                    return _llm(prompt)

                def report_b(prompt, t=task, v=variant):
                    if mode == "rule":
                        return json.dumps(rule_report(t, "agent_b", v), ensure_ascii=False)
                    return _llm(prompt)

                def plan_fn(prompt, t=task, v=variant, tr=track):
                    if mode == "rule":
                        marker = "【已送达约束报告】"
                        reports = {}
                        if marker in prompt:
                            raw = prompt.split(marker, 1)[1].split("\n", 1)[0].strip()
                            reports = json.loads(raw)
                        return json.dumps(rule_plan(t, v, reports, global_view=tr == "single"), ensure_ascii=False)
                    return _llm(prompt)

                def commit_a(prompt, t=task, v=variant):
                    if mode == "rule":
                        marker = "【联合方案】"
                        plan = json.loads(prompt.split(marker, 1)[1].strip()) if marker in prompt else None
                        return json.dumps(rule_commit(t, "agent_a", v, plan), ensure_ascii=False)
                    return _llm(prompt)

                def commit_b(prompt, t=task, v=variant):
                    if mode == "rule":
                        marker = "【联合方案】"
                        plan = json.loads(prompt.split(marker, 1)[1].strip()) if marker in prompt else None
                        return json.dumps(rule_commit(t, "agent_b", v, plan), ensure_ascii=False)
                    return _llm(prompt)

                loop = run_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    out_dir=out / "runs" / instance_id,
                    report_a_fn=report_a,
                    report_b_fn=report_b,
                    plan_fn=plan_fn,
                    commit_a_fn=commit_a,
                    commit_b_fn=commit_b,
                )
                cells.append(_score_and_store(task=task, variant=variant, track=track, repeat_id=repeat_id, loop=loop, out_dir=out, mode=mode))
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
    if args.phase == "rule":
        print("Rule 已过门。下一步 Direct，再用 --phase seed0。", flush=True)
        return 0
    from exp_gm_c1_01.fairness import preflight

    out = BRIDGE_ROOT / "output" / "exp_gm_c1_01_20260825"
    out.mkdir(parents=True, exist_ok=True)
    check = preflight()
    print("fairness_preflight", json.dumps({k: v for k, v in check.items() if k != "call_contract"}, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed; not freezing, not calling the model.", flush=True)
        return 1
    freeze = write_manifest(out)
    print("frozen", json.dumps({k: v for k, v in freeze.items() if k != "fairness_preflight"}, ensure_ascii=False), flush=True)
    print("phase=direct", flush=True)
    direct_cells = run_direct_cells(out, mode="llm")
    direct_full = _full_rate(direct_cells, "direct")
    direct_ok = (
        summarize_workflow(WORKFLOW_ID, direct_cells)["coverage"] == 1.0
        and len(direct_cells) == 6
        and _budget_ok(direct_cells, kinds=("direct_plan",))
        and direct_full == 1.0
    )
    (out / "direct_cells.json").write_text(
        json.dumps({"ok": direct_ok, "fullpass": direct_full, "cells": direct_cells}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"direct_ok={direct_ok} direct_fullpass={direct_full}", flush=True)
    if not direct_ok:
        _pack(direct_cells, out, phase="direct", gate="direct_fail", freeze=freeze, direct_ok=False, direct_fullpass=direct_full)
        print("Direct 未过。停止。不跑 Single/Multi/Drop。", flush=True)
        return 1
    if args.phase == "direct":
        print("Direct 已过。seed0 用 --phase seed0。", flush=True)
        return 0
    print("phase=seed0", flush=True)
    cells = run_repeat(out, 0, mode="llm")
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    gate = _seed0_gate(cells, coverage)
    payload = _pack(cells, out, phase="seed0", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。不补 54 格。", flush=True)
        return 1
    print(f"gate={gate}。第一轮只跑 18 格，不补 repeat 1/2，不建留出。", flush=True)
    print(payload["claim"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
