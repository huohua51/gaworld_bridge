#!/usr/bin/env python3
"""CAL-GM-L1-RESUME-01: Coordinator first-unfinished-step selection. Does not overwrite L1-01b."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from cal_gm_l1_resume_01.freeze import write_manifest
from cal_gm_l1_resume_01.loader import VARIANTS, load_tasks
from cal_gm_l1_resume_01.loop import run_cell
from cal_gm_l1_resume_01.prompts import agent_prompt, rule_agent
from cal_gm_l1_resume_01.rule_tests import main as rule_main
from cal_gm_l1_resume_01.scorer import metrics, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "cal_gm_l1_resume_01"
PROVIDER = "paratera_glm"
MODEL = "GLM-4-Flash"
TEMPERATURE = 0
EXPERIMENT_ID = "CAL-GM-L1-RESUME-01"
OUT = BRIDGE_ROOT / "output" / "cal_gm_l1_resume_01_20260825"


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
    loop = run_cell(
        task=task,
        variant=variant,
        instance_id=instance_id,
        out_dir=run_dir,
        prompt=agent_prompt(task, variant),
        generate_fn=generate_fn,
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
    cell["extra"] = extra
    cell["ranking_eligible"] = False
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cell


def _claim(summary: dict) -> str:
    if summary["rates"]["Coverage"] < 1.0:
        return "Coverage 未过，回到 R0。不解释 Coordinator 续做能力。"
    if summary["pass_gate"]["holds"]:
        return "Coordinator 续做位置校准 18/18 通过。不覆盖 L1-01b。下一步才是新建 L1-01c 做完整多智能体回归。"
    return "组件校准未过。修 Coordinator 状态表达或提示契约，不重跑 L1，不补 L1-01b 的 54 格。"


def _pack(cells: list[dict], out: Path, *, phase: str, freeze: dict | None) -> dict:
    wf = summarize_workflow(WORKFLOW_ID, cells)
    wf["ranking_eligible"] = False
    scored = metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": EXPERIMENT_ID,
        "parent": "EXP-GM-L1-01b",
        "phase": phase,
        "ranking_eligible": False,
        "summary": wf,
        "metrics": scored,
        "claim": _claim(scored),
        "freeze": freeze,
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "model": MODEL if phase != "rule" else "rule",
        "temperature": TEMPERATURE,
        "does_not_overwrite": ["EXP-GM-L1-01", "EXP-GM-L1-01b"],
        "l1_01c_allowed": bool(scored["pass_gate"]["holds"] and len(cells) == 18),
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rates = scored["rates"]
    lines = [
        f"# {EXPERIMENT_ID}",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}",
        "- ranking_eligible：false",
        "- 构念：coordinator_resume_point_selection",
        "- 不覆盖 L1-01 / L1-01b",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        "| Coverage | ResumeStepAccuracy | CompletedStepNotRepeated | RemainingStepNotSkipped | ResumeContractValid | StrictPair |",
        "|---|---|---|---|---|---|",
        (
            f"| {rates['Coverage']} | {rates['ResumeStepAccuracy']} | {rates['CompletedStepNotRepeated']} | "
            f"{rates['RemainingStepNotSkipped']} | {rates['ResumeContractValid']} | {rates['StrictPair']} |"
        ),
        "",
        f"**结论：** {_claim(scored)}",
        "",
        "| instance | variant | valid | FullPass | resume | first_error |",
        "|---|---|---|---|---|---|",
    ]
    for cell in cells:
        extra = cell.get("extra") or {}
        action = extra.get("action") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('variant')} | {cell.get('measurement_valid')} | "
            f"{cell.get('full_pass')} | {action.get('resume_step')} | {(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import yaml

    (out / "GATE.yaml").write_text(
        yaml.safe_dump(
            {
                "experiment_id": EXPERIMENT_ID,
                "parent": "EXP-GM-L1-01b",
                "phase": phase,
                "pass_gate": scored["pass_gate"],
                "rates": rates,
                "claim": _claim(scored),
                "ranking_eligible": False,
                "l1_01c_allowed": payload["l1_01c_allowed"],
                "does_not_overwrite": ["EXP-GM-L1-01", "EXP-GM-L1-01b"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return payload


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells = []
    for task in load_tasks():
        for variant in VARIANTS:
            instance_id = f"{task['id']}_{variant}_r{repeat_id}"
            print(f"run {instance_id} mode={mode}", flush=True)
            cell = _score_one(task, variant, repeat_id, out, mode=mode)
            cells.append(cell)
            extra = cell.get("extra") or {}
            print(
                f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                f"resume={(extra.get('action') or {}).get('resume_step')} first_error={(cell.get('process_profile') or {}).get('first_error')}",
                flush=True,
            )
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "all"), default="all")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        print("Rule 未过门，停止 GLM。", flush=True)
        return 1
    if args.phase == "rule":
        print("Rule 已过门。18 格用 --phase all。", flush=True)
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = write_manifest(OUT)
    print("frozen", json.dumps({"base_commit": freeze.get("base_commit")}, ensure_ascii=False), flush=True)
    cells = []
    for repeat_id in (0, 1, 2):
        cells.extend(run_repeat(OUT, repeat_id, mode="llm"))
    payload = _pack(cells, OUT, phase="all", freeze=freeze)
    print((OUT / "REPORT.md").read_text(encoding="utf-8"))
    if not payload["metrics"]["pass_gate"]["holds"]:
        print("组件校准未过。不建 L1-01c，不重跑 L1。", flush=True)
        return 1
    print("18/18 通过。可以新建 L1-01c，不能覆盖 L1-01b。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
