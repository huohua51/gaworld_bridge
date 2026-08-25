#!/usr/bin/env python3
"""CAL-GM-C1-PRIORITY-01: priority preservation component calibration."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cal_gm_c1_priority_01.freeze import write_manifest
from cal_gm_c1_priority_01.loader import VARIANTS, load_tasks
from cal_gm_c1_priority_01.loop import run_cell
from cal_gm_c1_priority_01.prompts import rule_agent
from cal_gm_c1_priority_01.rule_tests import main as rule_main
from cal_gm_c1_priority_01.scorer import metrics, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "cal_gm_c1_priority_01"
PROVIDER = "paratera_glm"
MODEL = "GLM-4-Flash"
TEMPERATURE = 0
EXPERIMENT_ID = "CAL-GM-C1-PRIORITY-01"


def _pin_glm() -> None:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    providers = CONFIG.setdefault("llm", {}).setdefault("providers", {})
    glm = providers.setdefault(PROVIDER, {})
    if isinstance(glm, dict):
        glm["max_tokens"] = max(int(glm.get("max_tokens") or 0), 1024)
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
        generate_fn = lambda _p, t=task, v=variant: json.dumps(rule_agent(t, v), ensure_ascii=False)
    else:
        generate_fn = _llm
    loop = run_cell(task=task, variant=variant, instance_id=instance_id, out_dir=run_dir, generate_fn=generate_fn)
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
    cell["extra"] = extra
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cell


def _pack(cells: list[dict], out: Path, *, phase: str, freeze: dict | None) -> dict:
    wf = summarize_workflow(WORKFLOW_ID, cells)
    wf["ranking_eligible"] = False
    scored = metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "parent": "EXP-GM-C1-02",
        "ap_items": ["AP-C1-D-01"],
        "phase": phase,
        "ranking_eligible": False,
        "generalization_claim": False,
        "does_not_overwrite": "EXP-GM-C1-02",
        "summary": wf,
        "metrics": scored,
        "claim": scored["interpretation"],
        "freeze": freeze,
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "model": MODEL if phase != "rule" else "rule",
        "temperature": TEMPERATURE,
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rates = scored["rates"]
    split = scored["split"]
    lines = [
        "# CAL-GM-C1-PRIORITY-01",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}",
        "- 不覆盖 C1-02。不开 L1。不建留出。",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        f"| PriorityPreserved | {rates['PriorityPreserved']} |",
        f"| EarliestIdleLow | {rates['EarliestIdleLow']} |",
        f"| ActualFinalConflictFree | {rates['ActualFinalConflictFree']} |",
        f"| JointConstraintSatisfaction | {rates['JointConstraintSatisfaction']} |",
        f"| PolicyConstrainedPlan | {rates['PolicyConstrainedPlan']} |",
        f"| FullPass control | {split['control']} |",
        f"| FullPass intervention | {split['intervention']} |",
        f"| Coverage | {rates['Coverage']} |",
        "",
        f"- 解释：{scored['interpretation']}",
        f"- first_error：{payload['first_error']}",
        "",
        f"**结论：** {payload['claim']}",
        "",
        "| instance | variant | valid | FullPass | first_error |",
        "|---|---|---|---|---|",
    ]
    for cell in wf["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('variant')} | {cell.get('measurement_valid')} | "
            f"{cell.get('full_pass')} | {(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import yaml

    (out / "GATE.yaml").write_text(
        yaml.safe_dump(
            {
                "experiment_id": EXPERIMENT_ID,
                "parent": "EXP-GM-C1-02",
                "phase": phase,
                "ap_items": ["AP-C1-D-01"],
                "pass_gate": scored["pass_gate"],
                "rates": rates,
                "split": split,
                "interpretation": scored["interpretation"],
                "ranking_eligible": False,
                "does_not_overwrite": "EXP-GM-C1-02",
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
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
                f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                flush=True,
            )
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "seed0", "all"), default="all")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    if args.phase == "rule":
        print("Rule 已过门。", flush=True)
        return 0
    out = BRIDGE_ROOT / "output" / "cal_gm_c1_priority_01_20260825"
    out.mkdir(parents=True, exist_ok=True)
    freeze = write_manifest(out)
    print("frozen", freeze.get("base_commit"), flush=True)
    print("phase=seed0", flush=True)
    cells = run_repeat(out, 0, mode="llm")
    payload = _pack(cells, out, phase="seed0", freeze=freeze)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if payload["metrics"]["rates"]["Coverage"] < 1.0:
        print("seed0 Coverage 未过。不补重复。", flush=True)
        return 1
    if args.phase == "seed0":
        print("seed0 完成。补 18 格用 --phase all。", flush=True)
        return 0
    print("phase=repeats", flush=True)
    cells.extend(run_repeat(out, 1, mode="llm"))
    cells.extend(run_repeat(out, 2, mode="llm"))
    payload = _pack(cells, out, phase="all", freeze=freeze)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0 if payload["metrics"]["pass_gate"]["holds"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
