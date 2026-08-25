#!/usr/bin/env python3
"""EXP-GM-N1 runner. Seed0 freezes hashes, then runs 18 cells and branches."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_n1.budget import MODEL, PROVIDER, TEMPERATURE
from exp_gm_n1.fairness import preflight
from exp_gm_n1.freeze import write_manifest
from exp_gm_n1.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_n1.loop import run_cell
from exp_gm_n1.prompts import rule_decision, rule_relay, rule_source
from exp_gm_n1.rule_tests.calibrate import main as rule_main
from exp_gm_n1.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_n1_delivery"


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


def _rule_fns(task: dict, variant: str):
    def source_fn(_p: str) -> str:
        return json.dumps(rule_source(task, variant), ensure_ascii=False)

    def relay_fn(_p: str) -> str:
        payload = rule_source(task, variant)
        return json.dumps(rule_relay(task, [payload], task["source_id"]), ensure_ascii=False)

    def decision_fn(prompt: str) -> str:
        marker = "【收件箱】"
        inbox = []
        if marker in prompt:
            raw = prompt.split(marker, 1)[1].split("\n【", 1)[0].strip()
            inbox = json.loads(raw)
        return json.dumps(rule_decision(task, inbox=inbox), ensure_ascii=False)

    return source_fn, relay_fn, decision_fn


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


def _full_rate(cells: list[dict], track: str) -> float | None:
    subset = [c for c in _valid(cells, track) if c.get("full_pass") is not None]
    if not subset:
        return None
    return round(sum(int(c["full_pass"]) for c in subset) / len(subset), 4)


def _budget_ok(cells: list[dict]) -> bool:
    return bool(cells) and all((c.get("extra") or {}).get("budget_calls") == 3 for c in cells)


def _isolation_ok(cells: list[dict]) -> bool:
    for cell in cells:
        extra = cell.get("extra") or {}
        if not extra.get("relay_ran"):
            return False
        if extra.get("track") == "drop" and extra.get("executor_saw_message"):
            return False
        if extra.get("track") in {"direct", "full"} and extra.get("variant") == "intervention" and extra.get("executor_saw_message") is False:
            return False
    return bool(cells)


def _seed0_gate(cells: list[dict], coverage: float) -> str:
    if coverage < 1.0 or len(cells) < 18:
        return "A_r0"
    if not _budget_ok(cells) or not _isolation_ok(cells):
        return "A_r0"
    direct = _full_rate(cells, "direct")
    full = _full_rate(cells, "full")
    drop = _full_rate(cells, "drop")
    if direct == 0.0 and full == 0.0:
        return "C_floor"
    if full == drop and direct == full:
        return "C_no_info_dependence"
    if direct == 1.0 and full == 1.0:
        return "C_ceiling_fill" if full == 1.0 and drop == 1.0 else "fill_repeats"
    return "fill_repeats"


def _pack(cells: list[dict], out: Path, *, phase: str, gate: str | None, freeze: dict | None) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-N1",
        "phase": phase,
        "gate": gate,
        "ranking_eligible": False,
        "freeze": freeze,
        "summary": summary,
        "fairness": {
            "coverage": summary["coverage"],
            "budget_ok": _budget_ok(cells),
            "isolation_ok": _isolation_ok(cells),
            "direct_full": _full_rate(cells, "direct"),
            "full_full": _full_rate(cells, "full"),
            "drop_full": _full_rate(cells, "drop"),
        },
        "first_error": dict(Counter((c.get("process_profile") or {}).get("first_error") for c in cells)),
        "model": MODEL,
        "temperature": TEMPERATURE,
        "note": "seed0 先看测量门，不宣布多Agent或信息传播价值。",
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "cell_table_seed0.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fair = payload["fairness"]
    lines = [
        "# EXP-GM-N1",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；gate：{gate}",
        "- ranking_eligible：false",
        f"- 冻结：{(freeze or {}).get('base_commit')}",
        "",
        "## 测量门",
        "",
        f"- Coverage：{fair['coverage']}",
        f"- 预算均为 3 次：{fair['budget_ok']}",
        f"- Drop 隔离且 Relay 实际运行：{fair['isolation_ok']}",
        f"- FullPass Direct / Full / Drop：{fair['direct_full']} / {fair['full_full']} / {fair['drop_full']}",
        "",
        f"- first_error：{payload['first_error']}",
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
    if gate == "A_r0":
        lines.extend(["", "**分支：** Coverage 或公平性未过，停止。信息价值 N/A。不改提示重跑。"])
    elif gate == "C_floor":
        lines.extend(["", "**分支：** Direct 与 Full 共同地板。不能解释成信息传播无价值。"])
    elif gate == "C_no_info_dependence":
        lines.extend(["", "**分支：** Full 与 Drop 无差异，需检查任务是否存在真实信息依赖。"])
    elif gate in {"fill_repeats", "completed_repeats", "C_ceiling_fill"}:
        lines.extend(["", "**分支：** Coverage 通过。不在 seed0 宣布信息传播价值。"])
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if phase == "seed0":
        (out / "REPORT_seed0.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def run_repeat(out: Path, repeat_id: int, *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                instance_id = f"{task['id']}_{variant}_{track}_r{repeat_id}"
                print(f"run {instance_id} mode={mode}", flush=True)
                if mode == "rule":
                    source_fn, relay_fn, decision_fn = _rule_fns(task, variant)
                else:
                    source_fn = relay_fn = decision_fn = _llm
                loop = run_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    task_id=instance_id,
                    out_dir=out / "runs" / instance_id,
                    source_fn=source_fn,
                    relay_fn=relay_fn,
                    decision_fn=decision_fn,
                )
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
                (out / "runs" / instance_id / "cell_result.json").write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                cells.append(cell)
                print(
                    f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                    f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                    flush=True,
                )
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("rule", "seed0"), default="rule")
    args = parser.parse_args()
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    print("phase=rule", flush=True)
    if rule_main() != 0:
        return 1
    if args.phase == "rule":
        print("Rule 已过门。seed0 用 --phase seed0。", flush=True)
        return 0

    out = BRIDGE_ROOT / "output" / "exp_gm_n1_20260825"
    out.mkdir(parents=True, exist_ok=True)
    check = preflight()
    print("fairness_preflight", json.dumps(check, ensure_ascii=False), flush=True)
    if not check["ok"]:
        print("fairness preflight failed; not freezing, not calling the model.", flush=True)
        return 1
    freeze = write_manifest(out)
    print("frozen", json.dumps(freeze, ensure_ascii=False), flush=True)
    print("phase=seed0", flush=True)
    cells = run_repeat(out, 0, mode="llm")
    gate = _seed0_gate(cells, summarize_workflow(WORKFLOW_ID, cells)["coverage"])
    payload = _pack(cells, out, phase="seed0", gate=gate, freeze=freeze)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if gate == "A_r0":
        print("gate=A_r0，停止。", flush=True)
        return 1
    if gate == "C_floor":
        print("gate=C_floor，停止。不能解释成信息传播无价值。", flush=True)
        return 0
    if gate == "C_no_info_dependence":
        print("gate=C_no_info_dependence，检查任务信息依赖后再决定是否补重复。", flush=True)
        return 0
    print("phase=repeats", flush=True)
    cells.extend(run_repeat(out, 1, mode="llm"))
    cells.extend(run_repeat(out, 2, mode="llm"))
    payload = _pack(cells, out, phase="all", gate="completed_repeats", freeze=freeze)
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0 if payload["summary"]["coverage"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
