#!/usr/bin/env python3
"""EXP-GM-C1-03. Full Multi retry regression. Direct is solvability only."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_c1_03.budget import KINDS, MODEL, PROVIDER, TEMPERATURE
from exp_gm_c1_03.freeze import write_manifest
from exp_gm_c1_03.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_c1_03.loop import run_cell, run_direct
from exp_gm_c1_03.prompts import rule_commit, rule_direct, rule_plan_from_reports, rule_report
from exp_gm_c1_03.rule_tests import main as rule_main
from exp_gm_c1_03.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_c1_03_retry"
EXPERIMENT_ID = "EXP-GM-C1-03"


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
    prots = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_protection"]
    coords = [c for c in cells if (c.get("extra") or {}).get("track") == "drop_coordinator"]
    if not prots or not coords:
        return False
    for cell in prots:
        extra = cell.get("extra") or {}
        if extra.get("variant") == "intervention" and extra.get("protection_delivered"):
            return False
        if not extra.get("b_ran"):
            return False
    for cell in coords:
        extra = cell.get("extra") or {}
        if extra.get("plan_delivered"):
            return False
    return True


def _env_auto_repair(cells: list[dict]) -> int:
    return sum(int((c.get("extra") or {}).get("unregistered_modification") or 0) for c in cells)


def _seed0_gate(cells: list[dict], coverage: float, metrics: dict) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _budget_ok(cells) or not _isolation_ok(cells) or _env_auto_repair(cells) != 0:
        return "A_r0"
    nack = metrics.get("NackPathCoverageIntervention")
    if nack != 1.0:
        return "nack_path_missed"
    multi = _full_rate(cells, "multi")
    if multi == 0.0:
        return "C_floor"
    if metrics.get("RetryRecoverySuccess") != 1.0:
        return "retry_not_recovered"
    if metrics.get("ConstraintRegressionRate") != 0.0:
        return "constraint_regression"
    if multi == 1.0 and _full_rate(cells, "drop_protection") == 1.0 and _full_rate(cells, "drop_coordinator") == 1.0:
        return "C_ceiling"
    return "off_floor"


def _interpret(full: dict[str, float | None], metrics: dict) -> str:
    multi = full.get("multi")
    if multi is None:
        return "Coverage 不足，不解释。"
    if metrics.get("NackPathCoverageIntervention") != 1.0:
        return "真模型未进入 NACK 路径。不能关闭 AP-C1-D-01。不能把第一次提案通过写成重试已验证。"
    if metrics.get("RetryRecoverySuccess") != 1.0:
        return (
            "平台已让真模型进入 NACK 路径，但尚无一次可确认的成功恢复。"
            "不能把 ConstraintRegressionRate=0 写成修复完成。不能关闭 AP-C1-D-01。"
        )
    if metrics.get("ConstraintRegressionRate") not in {0.0, 0}:
        return "修复优先级时重新引入资源冲突。不能关闭 AP-C1-D-01。"
    if multi == 0.0:
        return "Full Multi 处于地板。不能估计多智能体协调价值。不能说集体协调已通过。"
    if multi == 1.0:
        return "R0 有效且真模型进入 NACK 路径并恢复。有资格关闭 AP-C1-D-01。仍不能把 C1-02 原分改写为已通过。"
    return "Full Multi 未处于地板。按首错定位重试恢复。不能提前说集体协调已经通过。"


def _metrics(cells: list[dict]) -> dict:
    full = {track: _full_rate(cells, track) for track in TRACKS}
    inter_multi = _valid(cells, "multi", "intervention")
    nack = _mean(inter_multi, "nack_path_coverage")
    recovery = _mean(inter_multi, "retry_recovery_success")
    regression = _mean(inter_multi, "constraint_regression")
    n = len(inter_multi)
    nack_n = sum(int(bool((c.get("extra") or {}).get("nack_path_coverage"))) for c in inter_multi)
    recovered_n = sum(int(bool((c.get("extra") or {}).get("retry_recovery_success"))) for c in inter_multi)
    contract_n = sum(int(bool((c.get("extra") or {}).get("retry_plan_version_invalid"))) for c in inter_multi)
    not_adapted_n = sum(1 for c in inter_multi if (c.get("process_profile") or {}).get("first_error") == "retry_not_recovered")
    payload = {
        "Coverage": {track: _coverage_track(cells, track) for track in TRACKS},
        "ActualFinalConflictFree": {track: _mean(_valid(cells, track), "actual_final_conflict_free") for track in TRACKS},
        "JointConstraintSatisfaction": {track: _mean(_valid(cells, track), "joint_constraint_satisfaction") for track in TRACKS},
        "JointPlanCommitted": {track: _mean(_valid(cells, track), "joint_plan_committed") for track in TRACKS},
        "ExecutionMatchesPlan": {track: _mean(_valid(cells, track), "execution_matches_plan") for track in TRACKS},
        "ProtectedAssignmentRetention": {track: _mean(_valid(cells, track), "protected_assignment_retention") for track in TRACKS},
        "LowPriorityReallocationCorrect": {track: _mean(_valid(cells, track), "low_priority_reallocation_correct") for track in TRACKS},
        "NackPathCoverageIntervention": nack,
        "RetryRecoverySuccess": recovery,
        "ConstraintRegressionRate": regression,
        "constraint_regression_not_success": True,
        "nack_path_exercised": f"{nack_n}/{n}" if n else "0/0",
        "retry_evaluable": f"{n}/{n}" if n else "0/0",
        "retry_recovered": f"{recovered_n}/{n}" if n else "0/0",
        "retry_contract_failure": f"{contract_n}/{n}" if n else "0/0",
        "retry_not_adapted": f"{not_adapted_n}/{n}" if n else "0/0",
        "EnvironmentAutoRepair": _env_auto_repair(cells),
        "FullPass": full,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "floor": full["multi"] == 0.0,
        "ceiling": full["multi"] == 1.0 and full["drop_protection"] == 1.0 and full["drop_coordinator"] == 1.0,
    }
    payload["interpretation"] = _interpret(full, payload)
    return payload


def _claim(gate: str, metrics: dict, *, direct_ok: bool) -> str:
    if not direct_ok:
        return "Direct 不可做。停止。Direct 不是正式系统结果。不解释 Multi。"
    if gate == "A_r0":
        return "Coverage 或公平性未过，回到 R0。不解释能力。不关闭 AP-C1-D-01。"
    if gate == "nack_path_missed":
        return "真模型未进入 NACK 路径。不能关闭 AP-C1-D-01。C1-02 维持原分。"
    if gate == "retry_not_recovered":
        return "进入 NACK 后未恢复。不能关闭 AP-C1-D-01。"
    if gate == "constraint_regression":
        return "重试重新引入资源冲突。不能关闭 AP-C1-D-01。"
    if gate == "C_floor":
        return "Full Multi 共地板。不能估计多智能体价值。不能说集体协调已通过。"
    if gate == "C_ceiling":
        return "三轨都高：Drop 无效或任务不依赖交付。不补 54 格。"
    return metrics.get("interpretation") or "按指标拆开报告。不能提前说集体协调已经通过。"


def _pack(cells: list[dict], out: Path, *, phase: str, gate: str | None, freeze: dict | None, direct_ok: bool, direct_fullpass: float | None) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "parent": "CAL-GM-C1-PRIORITY-02",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "generalization_claim": False,
        "direct_ok": direct_ok,
        "direct_fullpass": direct_fullpass,
        "direct_is_formal_result": False,
        "primary_track": "multi",
        "does_not_overwrite": ["EXP-GM-C1-02", "CAL-GM-C1-PRIORITY-01", "CAL-GM-C1-PRIORITY-02"],
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
        "# EXP-GM-C1-03",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- 正式对象：Full Multi。Direct 非正式结果。不覆盖 C1-02。",
        "- ranking_eligible：false",
        f"- Direct 可做：{direct_ok}（FullPass={direct_fullpass}，仅校准）",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        f"- NackPathCoverageIntervention：{m['NackPathCoverageIntervention']}",
        f"- nack_path_exercised：{m['nack_path_exercised']}",
        f"- retry_evaluable：{m['retry_evaluable']}",
        f"- retry_recovered：{m['retry_recovered']}",
        f"- retry_contract_failure：{m['retry_contract_failure']}",
        f"- retry_not_adapted：{m['retry_not_adapted']}",
        f"- RetryRecoverySuccess：{m['RetryRecoverySuccess']}",
        f"- ConstraintRegressionRate：{m['ConstraintRegressionRate']}（重试未恢复时不得单独强调为好结果）",
        f"- EnvironmentAutoRepair：{m['EnvironmentAutoRepair']}",
        "",
        "| 指标 | Multi | DropProtection | DropCoordinator |",
        "|---|---:|---:|---:|",
        f"| Coverage | {m['Coverage']['multi']} | {m['Coverage']['drop_protection']} | {m['Coverage']['drop_coordinator']} |",
        f"| ActualFinalConflictFree | {m['ActualFinalConflictFree']['multi']} | {m['ActualFinalConflictFree']['drop_protection']} | {m['ActualFinalConflictFree']['drop_coordinator']} |",
        f"| ProtectedAssignmentRetention | {m['ProtectedAssignmentRetention']['multi']} | {m['ProtectedAssignmentRetention']['drop_protection']} | {m['ProtectedAssignmentRetention']['drop_coordinator']} |",
        f"| LowPriorityReallocationCorrect | {m['LowPriorityReallocationCorrect']['multi']} | {m['LowPriorityReallocationCorrect']['drop_protection']} | {m['LowPriorityReallocationCorrect']['drop_coordinator']} |",
        f"| FullPass | {m['FullPass']['multi']} | {m['FullPass']['drop_protection']} | {m['FullPass']['drop_coordinator']} |",
        f"| StrictPair | {m['StrictPair']['multi']} | {m['StrictPair']['drop_protection']} | {m['StrictPair']['drop_coordinator']} |",
        "",
        f"- first_error：{m['first_error']}",
        f"- 解释：{m['interpretation']}",
        "",
        f"**结论：** {payload['claim']}",
        "",
        "| instance | valid | FullPass | track | nack | first_error |",
        "|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('track')} | {extra.get('nack_path_coverage')} | {(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if phase in {"seed0", "seed0_planid_rescore"}:
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
                "nack_path_coverage_intervention": m["NackPathCoverageIntervention"],
                "retry_recovery_success": m["RetryRecoverySuccess"],
                "nack_path_exercised": m["nack_path_exercised"],
                "retry_evaluable": m["retry_evaluable"],
                "retry_recovered": m["retry_recovered"],
                "retry_contract_failure": m["retry_contract_failure"],
                "retry_not_adapted": m["retry_not_adapted"],
                "constraint_regression_rate": m["ConstraintRegressionRate"],
                "constraint_regression_not_success": True,
                "environment_auto_repair": m["EnvironmentAutoRepair"],
                "drop_protection_fullpass": m["FullPass"]["drop_protection"],
                "drop_coordinator_fullpass": m["FullPass"]["drop_coordinator"],
                "interpretation": m["interpretation"],
                "holdout": "not_created",
                "does_not_overwrite": ["EXP-GM-C1-02", "CAL-GM-C1-PRIORITY-01", "CAL-GM-C1-PRIORITY-02"],
                "claim": payload["claim"],
                "ranking_eligible": False,
                "ap_c1_d_01_closable": bool(
                    direct_ok
                    and gate not in {"A_r0", "nack_path_missed", "retry_not_recovered", "constraint_regression", "C_floor"}
                    and m["NackPathCoverageIntervention"] == 1.0
                    and m["RetryRecoverySuccess"] == 1.0
                    and m["ConstraintRegressionRate"] == 0.0
                    and m["FullPass"]["multi"] == 1.0
                ),
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
        f"nack={extra.get('nack_path_coverage')} first_error={(cell.get('process_profile') or {}).get('first_error')}",
        flush=True,
    )
    return cell


def _fns(task, variant, mode: str):
    def report_a(prompt):
        return json.dumps(rule_report(task, "agent_a", variant), ensure_ascii=False) if mode == "rule" else _llm(prompt)

    def report_b(prompt):
        return json.dumps(rule_report(task, "agent_b", variant), ensure_ascii=False) if mode == "rule" else _llm(prompt)

    def initial_fn(prompt):
        if mode != "rule":
            return _llm(prompt)
        marker = "【已送达初始报告】"
        reports = json.loads(prompt.split(marker, 1)[1].split("\n", 1)[0].strip()) if marker in prompt else {}
        return json.dumps(rule_plan_from_reports(task, reports, version="plan-init", variant=variant, stage="phase1"), ensure_ascii=False)

    def retry_fn(prompt):
        if mode != "rule":
            return _llm(prompt)
        marker = "【已送达初始报告】"
        reports = json.loads(prompt.split(marker, 1)[1].split("\n", 1)[0].strip()) if marker in prompt else {}
        stage = "final" if "【登记保护修订】" in prompt else "phase1"
        return json.dumps(rule_plan_from_reports(task, reports, version="plan-001", variant=variant, stage=stage), ensure_ascii=False)

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

    return report_a, report_b, initial_fn, retry_fn, commit_a, commit_b


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
                report_a, report_b, initial_fn, retry_fn, commit_a, commit_b = _fns(task, variant, mode)
                loop = run_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    out_dir=out / "runs" / instance_id,
                    report_a_fn=report_a,
                    report_b_fn=report_b,
                    initial_fn=initial_fn,
                    retry_fn=retry_fn,
                    commit_a_fn=commit_a,
                    commit_b_fn=commit_b,
                )
                cells.append(_score_and_store(task=task, variant=variant, track=track, repeat_id=repeat_id, loop=loop, out_dir=out, mode=mode))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "direct", "seed0", "all", "rescore"), default="seed0")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    if args.phase == "rule":
        print("Rule 已过门。", flush=True)
        return 0
    if args.phase == "rescore":
        import shutil
        import yaml

        from exp_gm_c1_03.rescore import rescore_seed0

        out = BRIDGE_ROOT / "output" / "exp_gm_c1_03_20260825"
        if (out / "GATE.yaml").is_file() and not (out / "GATE.pre_planid_rescore.yaml").is_file():
            shutil.copy(out / "GATE.yaml", out / "GATE.pre_planid_rescore.yaml")
        if (out / "REPORT.md").is_file() and not (out / "REPORT.pre_planid_rescore.md").is_file():
            shutil.copy(out / "REPORT.md", out / "REPORT.pre_planid_rescore.md")
        cells = rescore_seed0()
        freeze = yaml.safe_load((out / "FREEZE.yaml").read_text(encoding="utf-8")) if (out / "FREEZE.yaml").is_file() else {}
        coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
        metrics = _metrics(cells)
        gate = _seed0_gate(cells, coverage, metrics)
        _pack(cells, out, phase="seed0_planid_rescore", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=1.0)
        print((out / "REPORT.md").read_text(encoding="utf-8"))
        print(f"gate={gate}。离线重评分完成。不关闭 AP-C1-D-01。", flush=True)
        return 0 if gate not in {"A_r0"} else 1
    from exp_gm_c1_03.fairness import preflight

    out = BRIDGE_ROOT / "output" / "exp_gm_c1_03_20260825"
    out.mkdir(parents=True, exist_ok=True)
    check = preflight()
    print("fairness_preflight", json.dumps({"ok": check["ok"], "n_leaks": len(check["leaks"])}, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed", check["leaks"], flush=True)
        return 1
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
    metrics = _metrics(cells)
    gate = _seed0_gate(cells, coverage, metrics)
    _pack(cells, out, phase="seed0", gate=gate, freeze=freeze, direct_ok=True, direct_fullpass=direct_full)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。不关闭 AP-C1-D-01。", flush=True)
        return 1
    if gate == "nack_path_missed":
        print("真模型未进入 NACK 路径。不关闭 AP-C1-D-01。", flush=True)
        return 1
    if args.phase == "seed0":
        print(f"gate={gate}。seed0 完成。", flush=True)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
