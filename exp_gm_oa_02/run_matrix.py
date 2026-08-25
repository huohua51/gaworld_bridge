#!/usr/bin/env python3
"""EXP-GM-OA-02: exclusive keep/revise. Frozen OA-01 baseline is read, not rerun."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_oa_01.loader import VARIANTS, load_tasks
from exp_gm_oa_02.baseline import load_oa01_need_change_gate, oa01_baseline_metrics
from exp_gm_oa_02.loop import run_cell_loop
from exp_gm_oa_02.prompts import agent_prompt, parse_json_object, rule_agent
from exp_gm_oa_02.rule_controls import main as rule_main
from exp_gm_oa_02.scorer import (
    action_selection_accuracy,
    adaptation_rate,
    contract_failure_rate,
    control_stability_rate,
    coverage,
    oracle_conditioned_full_pass,
    score_cell,
    target_correct_rate,
)
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_oa_02_exclusive_action"
PROVIDER = "paratera_glm"
MODEL = "GLM-4-Flash"
TEMPERATURE = 0
PASS_GATE = {
    "coverage": 1.0,
    "control_stability_rate": 1.0,
    "adaptation_rate": 1.0,
    "contract_failure_rate": 0.0,
}


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


def _rule_fn(task: dict):
    def agent(notice, _plan):
        return rule_agent(task, notice)

    return agent


def _llm_fn(task: dict):
    def agent(notice, plan):
        text = _llm(agent_prompt(task, notice=notice or {}, plan=plan))
        try:
            return parse_json_object(text)
        except (ValueError, json.JSONDecodeError):
            return {}

    return agent


def _score_one(task: dict, variant: str, seed: int, out_root: Path, *, mode: str) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    apply_eval_mode_runtime(CONFIG)
    instance_id = f"{task['id']}_{variant}_exclusive_keep_revise_s{seed}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    loop = run_cell_loop(
        task=task,
        variant=variant,
        instance_id=instance_id,
        out_dir=run_dir,
        agent_fn=_rule_fn(task) if mode == "rule" else _llm_fn(task),
    )
    (run_dir / "raw_action.json").write_text(
        json.dumps(loop.get("raw_action") or loop.get("action") or {}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    cell = score_cell(
        task=task,
        variant=variant,
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


def _metrics(cells: list[dict]) -> dict:
    rates = {
        "Coverage": coverage(cells),
        "ActionSelectionAccuracy": action_selection_accuracy(cells),
        "ControlStabilityRate": control_stability_rate(cells),
        "AdaptationRate": adaptation_rate(cells),
        "ContractFailureRate": contract_failure_rate(cells),
        "TargetCorrect": target_correct_rate(cells),
        "OracleConditionedFullPass": oracle_conditioned_full_pass(cells),
    }
    gate = {
        "coverage_ok": rates["Coverage"] >= PASS_GATE["coverage"],
        "stability_ok": rates["ControlStabilityRate"] == PASS_GATE["control_stability_rate"],
        "adaptation_ok": rates["AdaptationRate"] == PASS_GATE["adaptation_rate"],
        "contract_ok": rates["ContractFailureRate"] == PASS_GATE["contract_failure_rate"],
    }
    gate["holds"] = all(gate.values()) and all(v is not None for v in rates.values())
    return {"rates": rates, "pass_gate": gate}


def _claim(metrics: dict) -> str:
    if metrics["pass_gate"]["holds"]:
        return "将 keep 与 revise 拆成两个动作，消除了开发集中的无意义占位符失败。这还不等于过度适应机制已解决，暂不建留出题。"
    return "开发集未过预注册门，不能宣布动作接口改造完成，也不建留出题。"


def _pack(cells: list[dict], out: Path, *, phase: str, mode: str) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    baseline_cells = load_oa01_need_change_gate()
    baseline = oa01_baseline_metrics(baseline_cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-OA-02",
        "task_id": "TASK-OA-exclusive-keep-revise",
        "phase": phase,
        "mode": mode,
        "ranking_eligible": False,
        "oa01_frozen": True,
        "summary": summary,
        "metrics": metrics,
        "oa01_need_change_gate_baseline": baseline,
        "claim": _claim(metrics),
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new = metrics["rates"]
    old = baseline
    lines = [
        "# EXP-GM-OA-02 Exclusive keep / revise",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；mode：{mode}",
        "- ranking_eligible：false",
        "- OA-01 任务、结果、Scorer 冻结；旧协议 18 格读取 need_change_gate，不重跑。",
        "- 未改 GM-01 / GM-02；未建留出集；未开 GM-03。",
        "",
        "## 主报指标",
        "",
        "| 来源 | Coverage | ActionSelectionAccuracy | ControlStabilityRate | AdaptationRate | ContractFailureRate | TargetCorrect | OracleConditionedFullPass |",
        "|---|---|---|---|---|---|---|---|",
        (
            f"| OA-01 need_change_gate（冻结） | {old['Coverage']} | {old['ActionSelectionAccuracy']} | "
            f"{old['ControlStabilityRate']} | {old['AdaptationRate']} | {old['ContractFailureRate']} | "
            f"{old['TargetCorrect']} | {old['OracleConditionedFullPass']} |"
        ),
        (
            f"| OA-02 exclusive_keep_revise | {new['Coverage']} | {new['ActionSelectionAccuracy']} | "
            f"{new['ControlStabilityRate']} | {new['AdaptationRate']} | {new['ContractFailureRate']} | "
            f"{new['TargetCorrect']} | {new['OracleConditionedFullPass']} |"
        ),
        "",
        f"- 冻结基线说明：{old['note']}",
        "",
        "## 预注册通过条件（只看 OA-02 18 格）",
        "",
        f"- Coverage = {new['Coverage']}（要求 1.0）",
        f"- ControlStabilityRate = {new['ControlStabilityRate']}（要求 1.0）",
        f"- AdaptationRate = {new['AdaptationRate']}（要求 1.0）",
        f"- ContractFailureRate = {new['ContractFailureRate']}（要求 0）",
        f"- 通过：{metrics['pass_gate']['holds']}",
        "",
        f"**结论：** {_claim(metrics)}",
        "",
        "## 格子证据",
        "",
        "| instance | variant | valid | FullPass | action_sel | target_correct | contract_rejected | first_error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('variant')} | {cell.get('measurement_valid')} | "
            f"{cell.get('full_pass')} | {extra.get('action_selection_correct')} | {extra.get('target_correct')} | "
            f"{extra.get('contract_rejected')} | {(cell.get('process_profile') or {}).get('first_error')} |"
        )
    errors = Counter((c.get("process_profile") or {}).get("first_error") for c in cells)
    lines.extend(["", "## 首错节点", "", "| first_error | n |", "|---|---|"])
    for name, count in errors.most_common():
        lines.append(f"| {name} | {count} |")
    failures = [c for c in cells if c.get("full_pass") != 1]
    if failures:
        lines.extend(["", "## 失败格原始动作", ""])
        for cell in failures:
            extra = cell.get("extra") or {}
            lines.append(f"- `{cell.get('instance_id')}` first_error={(cell.get('process_profile') or {}).get('first_error')}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(extra.get("action") or {}, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def run_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in load_tasks():
        for variant in VARIANTS:
            for seed in seeds:
                print(f"run {task['id']} variant={variant} seed={seed} mode={mode}", flush=True)
                cell = _score_one(task, variant, seed, out, mode=mode)
                cells.append(cell)
                extra = cell.get("extra") or {}
                print(
                    f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                    f"action_sel={extra.get('action_selection_correct')} "
                    f"contract_rejected={extra.get('contract_rejected')} "
                    f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
                if mode == "llm" and not cell.get("measurement_valid"):
                    return cells
    return cells


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", PROVIDER)
    out = BRIDGE_ROOT / "output" / "exp_gm_oa_02_20260824"
    out.mkdir(parents=True, exist_ok=True)

    print("phase=rule", flush=True)
    if rule_main() != 0:
        print("Rule 未过门，停止 GLM。", flush=True)
        return 1
    rule_cells = run_matrix(out / "rule", [0], mode="rule")
    _pack(rule_cells, out / "rule", phase="rule", mode="rule")
    print((out / "rule" / "REPORT.md").read_text(encoding="utf-8"))

    print("phase=seed0", flush=True)
    cells = run_matrix(out, [0], mode="llm")
    payload = _pack(cells, out, phase="seed0", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if payload["metrics"]["rates"]["Coverage"] < 1.0 or len(cells) < 6:
        print("seed0 Coverage 未到 1.0，停在测量门，不补重复。", flush=True)
        return 1
    print("phase=repeats", flush=True)
    cells.extend(run_matrix(out, [1, 2], mode="llm"))
    payload = _pack(cells, out, phase="all", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0 if payload["metrics"]["rates"]["Coverage"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
