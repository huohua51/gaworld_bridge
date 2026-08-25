#!/usr/bin/env python3
"""EXP-GM-04e-E: typed-patch Executor only. Stop if adoption does not rise."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04e.executor import executor_prompt, rule_executor
from exp_gm_04e.loop_e import run_executor_cell
from exp_gm_04e.scoring import r0_executor, rate
from exp_gm_04e.tasks import TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "exp_gm_04e_e_executor_only"
PROTOCOLS = ("legacy", "evidence_bound")
EXECUTOR_ID = 5


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault("paratera_glm", {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 2048)
        glm["temperature"] = 0
    routing = CONFIG.setdefault("llm", {}).setdefault("routing", {})
    routing["default"] = "paratera_glm"
    tasks = dict(routing.get("tasks") or {})
    tasks["schedule"] = "paratera_glm"
    routing["tasks"] = tasks
    os.environ["GAWORLD_LLM_PROVIDER"] = "paratera_glm"


def _llm(prompt: str) -> str:
    _pin_glm()
    from config import CONFIG
    from llm_providers import LLMRouter

    return LLMRouter(CONFIG).call(prompt, task="interview") or ""


def _llm_executor(task: dict, protocol: str, out_dir: Path):
    from gaworld.work.adapters.base import AdapterContext
    from gaworld.work.adapters.code import CodeAdapter
    from gaworld.work.schemas import WorkBrief

    def _fn(source: str) -> str:
        brief = WorkBrief(
            task_id=f"{task['id']}_{protocol}_exec",
            agent_id=EXECUTOR_ID,
            sim_day=1,
            sim_time="10:00",
            activity="工作",
            chosen_action="编写 Python 脚本",
            deliverable="py_script",
            adapter="code",
            brief_text=executor_prompt(task, source, protocol=protocol),
            estimated_minutes=15,
            submitted_at=time.time(),
        )
        ctx = AdapterContext(artifacts_root=str(out_dir / "adapter_calls"), llm=_llm, config={})
        result = CodeAdapter().run(brief, ctx)
        paths = result.artifact_paths or []
        if not paths or not os.path.isfile(paths[0]):
            return ""
        return Path(paths[0]).read_text(encoding="utf-8")

    return _fn


def _score_cell(task: dict, protocol: str, seed: int, out_root: Path, *, mode: str) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    cfg = CONFIG
    cfg.setdefault("eval_mode", {})
    cfg["eval_mode"]["enabled"] = True
    apply_eval_mode_runtime(cfg)

    instance_id = f"{task['id']}_{protocol}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    if mode == "rule":
        executor_fn = lambda source: rule_executor(task, protocol=protocol, source=source)
    else:
        executor_fn = _llm_executor(task, protocol, run_dir)
    loop = run_executor_cell(
        task=task,
        protocol=protocol,
        task_id=instance_id,
        out_dir=run_dir,
        executor_fn=executor_fn,
    )
    artifact = str(run_dir / "final_main.py")
    v2 = score_hidden_tests(artifact, task["v2"]["oracle"])
    v1 = score_hidden_tests(artifact, task["v1"]["oracle"])
    applied = bool(loop.get("patch_applied"))
    tests_ok = bool(v2.get("passed")) and not bool(v1.get("passed"))
    first_error = loop.get("first_error") or "none"
    if applied and not tests_ok:
        first_error = "artifact_test_failed"
    r0, r0_detail = r0_executor(loop)
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0", detail=r0_detail),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("fields_extractable", True, layer="R0", detail="executor-only cell executed"),
        ],
        artifact_gates=[
            GateResult("executor_only", True, layer="R1", detail="reviewer is rule-supplied patch"),
            GateResult("environment_did_not_rewrite", not loop.get("environment_rewrote"), layer="R1"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="patch_applied",
                layer="R2",
                scorer="artifact_value",
                evaluable=True,
                score=1.0 if applied else 0.0,
                passed=applied,
                critical=True,
            ),
        ],
        process_profile={"first_error": first_error, "events": loop.get("events")},
        extra={
            "task_id": task["id"],
            "protocol": protocol,
            "seed": seed,
            "mode": mode,
            "split": "development",
            "patch_applied": applied,
            "tests_ok": tests_ok,
            "verify": loop.get("verify"),
            "patches": loop.get("patches"),
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cell


def _pack(cells: list[dict], out: Path) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    old = rate(cells, "patch_applied", protocol="legacy")
    new = rate(cells, "patch_applied", protocol="evidence_bound")
    tests_old = rate(cells, "tests_ok", protocol="legacy")
    tests_new = rate(cells, "tests_ok", protocol="evidence_bound")
    advance = bool(
        old is not None
        and new is not None
        and summary.get("coverage") == 1.0
        and (new > old or (new == 1.0 and old == 1.0))
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-04e",
        "phase": "04e-E",
        "ranking_eligible": False,
        "held_out_run": False,
        "summary": summary,
        "patch_adoption_rate_old": old,
        "patch_adoption_rate_new": new,
        "tests_ok_rate_old": tests_old,
        "tests_ok_rate_new": tests_new,
        "advance_to_04e_full": advance,
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# EXP-GM-04e-E Typed-patch Executor",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 阶段：04e-E，Rule Reviewer 提供正确 patch，只测 Executor",
        "- 开发集三题；留出题未触碰",
        "",
        "## 主结果",
        "",
        f"- requested：{summary['requested']}",
        f"- measurement_valid：{summary['measurement_valid']}",
        f"- PatchAdoptionRate 旧：{old} 新：{new}",
        f"- 隐式测试（v2过且v1不过）旧：{tests_old} 新：{tests_new}",
        f"- 进入 04e-Full：{advance}",
        "",
        "## 决策",
        "",
    ]
    if advance:
        report.append("开发集 Executor 过门。可以进入 04e-Full。")
    else:
        report.append("开发集 Executor 未过门。停止，不跑 Full，不跑留出题。")
    report += [
        "",
        "| instance | protocol | valid | applied | tests_ok | first_error |",
        "|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        report.append(
            f"| {cell.get('instance_id')} | {extra.get('protocol')} | {cell.get('measurement_valid')} | "
            f"{extra.get('patch_applied')} | {extra.get('tests_ok')} | "
            f"{(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def run_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in TASKS:
        for protocol in PROTOCOLS:
            for seed in seeds:
                print(f"run {task['id']} protocol={protocol} seed={seed} mode={mode}", flush=True)
                cell = _score_cell(task, protocol, seed, out, mode=mode)
                cells.append(cell)
                extra = cell.get("extra") or {}
                print(
                    f"  valid={cell.get('measurement_valid')} applied={extra.get('patch_applied')} "
                    f"tests_ok={extra.get('tests_ok')} "
                    f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
    return cells


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    _pin_glm()
    out = BRIDGE_ROOT / "output" / "exp_gm_04e_e_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells = run_matrix(out, [0, 1, 2], mode="llm")
    payload = _pack(cells, out)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if not payload["advance_to_04e_full"]:
        print("04e-E 未过门，停止。", flush=True)
        return 1
    print("04e-E 过门。下一步才是 04e-Full。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
