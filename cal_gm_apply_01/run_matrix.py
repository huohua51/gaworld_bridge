#!/usr/bin/env python3
"""CAL-GM-APPLY-01: complete adoption. Reviewer/decision are Rule; model is Executor only."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cal_gm_apply_01.freeze import write_manifest
from cal_gm_apply_01.loader import VARIANTS, load_tasks
from cal_gm_apply_01.loop import run_cell
from cal_gm_apply_01.prompts import rule_executor
from cal_gm_apply_01.rule_tests import main as rule_main
from cal_gm_apply_01.scorer import metrics, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "cal_gm_apply_01"
PROVIDER = "paratera_glm"
MODEL = "GLM-4-Flash"
TEMPERATURE = 0
EXPERIMENT_ID = "CAL-GM-APPLY-01"


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


def _score_one(task: dict, variant: str, repeat_id: int, out_root: Path, *, mode: str) -> dict:
    instance_id = f"{task['id']}_{variant}_r{repeat_id}"
    run_dir = out_root / "runs" / instance_id
    if mode == "rule":
        executor_fn = lambda _p, t=task, v=variant: rule_executor(t, v, t["draft"])
    else:
        executor_fn = _llm
    loop = run_cell(
        task=task,
        variant=variant,
        instance_id=instance_id,
        out_dir=run_dir,
        executor_fn=executor_fn,
    )
    cell = score_cell(
        task=task,
        variant=variant,
        repeat_id=repeat_id,
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


def _claim(summary: dict, *, phase: str) -> str:
    if summary["pass_gate"]["holds"]:
        if phase == "seed0":
            return "seed0 过预注册门。补齐三次重复后才能冻结协议。"
        return "Executor 在固定初稿+正确修改要求下能完整落实。这还不等于 T3 工作流已修复，也不建留出。"
    rates = summary["rates"]
    if (rates.get("PartialChangeRate") or 0) > 0:
        return "存在部分落实。不能靠环境补改未改字段。不建 T3-02，不建留出。"
    return "开发集未过预注册门。不能宣布完整落实已解决，不建 T3-02，不建留出。"


def _pack(cells: list[dict], out: Path, *, phase: str, freeze: dict | None) -> dict:
    wf = summarize_workflow(WORKFLOW_ID, cells)
    wf["ranking_eligible"] = False
    scored = metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "construct": "complete_change_adoption",
        "role": "executor_component_calibration",
        "phase": phase,
        "ranking_eligible": False,
        "summary": wf,
        "metrics": scored,
        "claim": _claim(scored, phase=phase),
        "freeze": freeze,
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "model": MODEL if phase != "rule" else "rule",
        "temperature": TEMPERATURE,
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "cell_table_seed0.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rates = scored["rates"]
    lines = [
        "# CAL-GM-APPLY-01",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}",
        "- ranking_eligible：false",
        "- 构念：complete_change_adoption；角色：executor_component_calibration",
        "- Reviewer / 决策：Rule；模型只做 Executor。Scorer 读取真实文件。",
        "- 未使用 T3/N1/04e 原题。",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        "## 主报指标",
        "",
        "| Coverage | FieldAdoptionRate | CompleteChangeAdoptionRate | PartialChangeRate | UnregisteredChangeRate | HiddenTestPass | AcknowledgementExecutionGap |",
        "|---|---|---|---|---|---|---|",
        (
            f"| {rates['Coverage']} | {rates['FieldAdoptionRate']} | {rates['CompleteChangeAdoptionRate']} | "
            f"{rates['PartialChangeRate']} | {rates['UnregisteredChangeRate']} | "
            f"{rates['HiddenTestPass']} | {rates['AcknowledgementExecutionGap']} |"
        ),
        "",
        "## 预注册门",
        "",
        f"- Coverage = {rates['Coverage']}（要求 1.0）",
        f"- FieldAdoptionRate = {rates['FieldAdoptionRate']}（要求 1.0）",
        f"- CompleteChangeAdoptionRate = {rates['CompleteChangeAdoptionRate']}（要求 1.0）",
        f"- PartialChangeRate = {rates['PartialChangeRate']}（要求 0）",
        f"- UnregisteredChangeRate = {rates['UnregisteredChangeRate']}（要求 0）",
        f"- HiddenTestPass = {rates['HiddenTestPass']}（要求 1.0）",
        f"- AcknowledgementExecutionGap = {rates['AcknowledgementExecutionGap']}（要求 0）",
        f"- 通过：{scored['pass_gate']['holds']}",
        "",
        f"**结论：** {_claim(scored, phase=phase)}",
        "",
        "## 格子证据",
        "",
        "| instance | variant | valid | FullPass | adopted | complete | partial | hidden | first_error |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for cell in wf["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('variant')} | {cell.get('measurement_valid')} | "
            f"{cell.get('full_pass')} | {extra.get('adopted_n')}/{extra.get('required_n')} | "
            f"{extra.get('complete')} | {extra.get('partial')} | {extra.get('hidden_test_pass')} | "
            f"{(cell.get('process_profile') or {}).get('first_error')} |"
        )
    errors = Counter((c.get("process_profile") or {}).get("first_error") for c in cells)
    lines.extend(["", "## 首错节点", "", "| first_error | n |", "|---|---|"])
    for name, count in errors.most_common():
        lines.append(f"| {name} | {count} |")
    failures = [c for c in cells if c.get("full_pass") != 1]
    if failures:
        lines.extend(["", "## 失败格文件实值", ""])
        for cell in failures:
            extra = cell.get("extra") or {}
            lines.append(f"- `{cell.get('instance_id')}` first_error={(cell.get('process_profile') or {}).get('first_error')}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(extra.get("got") or {}, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "REPORT_seed0.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in load_tasks():
        for variant in VARIANTS:
            instance_id = f"{task['id']}_{variant}_r{repeat_id}"
            print(f"run {instance_id} mode={mode}", flush=True)
            cell = _score_one(task, variant, repeat_id, out, mode=mode)
            cells.append(cell)
            extra = cell.get("extra") or {}
            print(
                f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                f"adopted={extra.get('adopted_n')}/{extra.get('required_n')} "
                f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                flush=True,
            )
    return cells


def _write_gate(out: Path, payload: dict) -> None:
    import yaml

    gate = {
        "experiment_id": EXPERIMENT_ID,
        "phase": payload["phase"],
        "pass_gate": payload["metrics"]["pass_gate"],
        "rates": payload["metrics"]["rates"],
        "claim": payload["claim"],
        "ranking_eligible": False,
    }
    (out / "GATE.yaml").write_text(yaml.safe_dump(gate, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "seed0", "all"), default="all")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", PROVIDER)

    print("phase=rule", flush=True)
    if rule_main() != 0:
        print("Rule 未过门，停止 GLM。", flush=True)
        return 1
    if args.phase == "rule":
        print("Rule 已过门。seed0 用 --phase seed0 或默认 all。", flush=True)
        return 0

    out = BRIDGE_ROOT / "output" / "cal_gm_apply_01_20260825"
    out.mkdir(parents=True, exist_ok=True)
    freeze = write_manifest(out)
    print("frozen", json.dumps(freeze, ensure_ascii=False), flush=True)
    print("phase=seed0", flush=True)
    cells = run_repeat(out, 0, mode="llm")
    payload = _pack(cells, out, phase="seed0", freeze=freeze)
    _write_gate(out, payload)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if not payload["metrics"]["pass_gate"]["holds"] or payload["metrics"]["rates"]["Coverage"] < 1.0:
        print("seed0 未过预注册门，停止。不补重复，不调这三道题。", flush=True)
        return 1
    if args.phase == "seed0":
        print("seed0 过门。补重复用 --phase all。", flush=True)
        return 0
    print("phase=repeats", flush=True)
    cells.extend(run_repeat(out, 1, mode="llm"))
    cells.extend(run_repeat(out, 2, mode="llm"))
    payload = _pack(cells, out, phase="all", freeze=freeze)
    _write_gate(out, payload)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0 if payload["metrics"]["pass_gate"]["holds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
