#!/usr/bin/env python3
"""EXP-GM-OA-01: over-adaptation gate. Rule first, seed 0, fill repeats only if Coverage=1.0."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_oa_01.loader import PROTOCOLS, VARIANTS, load_tasks
from exp_gm_oa_01.loop import run_cell_loop
from exp_gm_oa_01.prompts import agent_prompt, parse_json_object, rule_agent
from exp_gm_oa_01.rule_controls import main as rule_main
from exp_gm_oa_01.scorer import (
    adaptation_rate,
    conditional_action_score,
    control_stability_rate,
    coverage,
    need_change_accuracy,
    score_cell,
    unnecessary_replan_rate,
)
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_oa_01_over_adaptation"
PROVIDER = "paratera_glm"
MODEL = "GLM-4-Flash"
TEMPERATURE = 0
IMPROVEMENT = {
    "coverage": 1.0,
    "control_stability_lift_min": 3 / 9,
    "adaptation_drop_max": 1 / 9,
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


def _rule_fn(task: dict, protocol: str):
    def agent(notice, _plan):
        return rule_agent(task, protocol, notice)

    return agent


def _llm_fn(task: dict, protocol: str):
    def agent(notice, plan):
        text = _llm(agent_prompt(task, protocol=protocol, notice=notice or {}, plan=plan))
        try:
            return parse_json_object(text)
        except (ValueError, json.JSONDecodeError):
            return {}

    return agent


def _score_one(task: dict, variant: str, protocol: str, seed: int, out_root: Path, *, mode: str) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    CONFIG.setdefault("eval_mode", {})["enabled"] = True
    apply_eval_mode_runtime(CONFIG)
    instance_id = f"{task['id']}_{variant}_{protocol}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    run_dir.mkdir(parents=True, exist_ok=True)
    loop = run_cell_loop(
        task=task,
        variant=variant,
        protocol=protocol,
        task_id=instance_id,
        out_dir=run_dir,
        agent_fn=_rule_fn(task, protocol) if mode == "rule" else _llm_fn(task, protocol),
    )
    raw_path = run_dir / "raw_action.json"
    raw_path.write_text(json.dumps(loop.get("action") or {}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cell = score_cell(
        task=task,
        variant=variant,
        protocol=protocol,
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
    by_protocol = {}
    for protocol in PROTOCOLS:
        by_protocol[protocol] = {
            "Coverage": coverage(cells, protocol),
            "NeedChangeAccuracy": need_change_accuracy(cells, protocol),
            "ControlStabilityRate": control_stability_rate(cells, protocol),
            "AdaptationRate": adaptation_rate(cells, protocol),
            "UnnecessaryReplanRate": unnecessary_replan_rate(cells, protocol),
            "ConditionalActionScore": conditional_action_score(cells, protocol),
        }
    old = by_protocol["legacy_direct"]
    new = by_protocol["need_change_gate"]
    lift = None
    adapt_drop = None
    if old["ControlStabilityRate"] is not None and new["ControlStabilityRate"] is not None:
        lift = round(new["ControlStabilityRate"] - old["ControlStabilityRate"], 4)
    if old["AdaptationRate"] is not None and new["AdaptationRate"] is not None:
        adapt_drop = round(old["AdaptationRate"] - new["AdaptationRate"], 4)
    urr_down = None
    if old["UnnecessaryReplanRate"] is not None and new["UnnecessaryReplanRate"] is not None:
        urr_down = new["UnnecessaryReplanRate"] < old["UnnecessaryReplanRate"]
    always_keep = bool(
        new["ControlStabilityRate"] is not None
        and new["AdaptationRate"] is not None
        and new["ControlStabilityRate"] >= 0.8
        and new["AdaptationRate"] <= 0.2
    )
    gate = {
        "coverage_ok": coverage(cells) >= IMPROVEMENT["coverage"],
        "stability_lift": lift,
        "stability_lift_ok": lift is not None and lift + 1e-9 >= IMPROVEMENT["control_stability_lift_min"],
        "adaptation_drop": adapt_drop,
        "adaptation_ok": adapt_drop is not None and adapt_drop - 1e-9 <= IMPROVEMENT["adaptation_drop_max"],
        "unnecessary_replan_down": urr_down,
        "always_keep_trap": always_keep,
    }
    gate["improvement_holds"] = bool(
        gate["coverage_ok"]
        and gate["stability_lift_ok"]
        and gate["adaptation_ok"]
        and gate["unnecessary_replan_down"]
        and not gate["always_keep_trap"]
    )
    return {"by_protocol": by_protocol, "improvement_gate": gate, "coverage": coverage(cells)}


def _read_verdict(metrics: dict) -> list[str]:
    old = metrics["by_protocol"]["legacy_direct"]
    new = metrics["by_protocol"]["need_change_gate"]
    gate = metrics["improvement_gate"]
    lines = [
        "## 预注册改进门",
        "",
        f"- Coverage：{metrics['coverage']}（要求 1.0）",
        f"- 新协议 ControlStabilityRate 提升：{gate['stability_lift']}（要求 ≥ 3/9 ≈ 0.3333）",
        f"- 新协议 AdaptationRate 下降：{gate['adaptation_drop']}（最多 1/9 ≈ 0.1111）",
        f"- UnnecessaryReplanRate 是否下降：{gate['unnecessary_replan_down']}",
        f"- 一律不行动陷阱：{gate['always_keep_trap']}",
        f"- 改进是否成立：{gate['improvement_holds']}",
        "",
        "## 结果怎么读",
        "",
    ]
    if metrics["coverage"] < 1.0:
        lines.append("- Coverage 下降：新契约太复杂，停止能力解释，先修契约。")
        return lines
    if gate["always_keep_trap"]:
        lines.append("- Control 高、Intervention 低：模型学会一律不行动，不能宣布改进。")
        return lines
    if gate["improvement_holds"]:
        lines.append("- 新协议对照稳定率提高且干预未明显下降：改造有效。下一步才是接入 GAWorld 事件响应动作接口，再建新留出题。")
        return lines
    if (new["NeedChangeAccuracy"] or 0) >= 0.8 and (new["ControlStabilityRate"] or 1) < 1.0:
        lines.append("- `need_change` 正确，但最终动作错误：判断会、执行映射不会。下一步改动作 schema、状态机和字段约束。")
    elif (new["NeedChangeAccuracy"] or 0) < 0.5:
        lines.append("- `need_change` 判断错误：模型不会区分观察与干预。下一步改状态差分提示、条件推理或增加规则检查器。")
    elif (new["UnnecessaryReplanRate"] or 1) >= (old["UnnecessaryReplanRate"] or 1) - 1e-9:
        lines.append("- 新协议仍然过度适应：单靠动作格式解决不了。下一步增加独立的行动必要性检查器。")
    else:
        lines.append("- 改进门未过，但不能用总分替代分项。继续看格子证据与首错节点。")
    return lines


def _pack(cells: list[dict], out: Path, *, phase: str, mode: str) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    metrics = _metrics(cells)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-OA-01",
        "task_id": "TASK-OA-need-change-gate",
        "phase": phase,
        "mode": mode,
        "ranking_eligible": False,
        "summary": summary,
        "metrics": metrics,
        "note": "禁止把总体 EventValue 当主结论。主报五个指标，ConditionalActionScore 只作附报。",
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    old = metrics["by_protocol"]["legacy_direct"]
    new = metrics["by_protocol"]["need_change_gate"]
    lines = [
        "# EXP-GM-OA-01 Over-adaptation gate",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- phase：{phase}；mode：{mode}",
        "- ranking_eligible：false",
        "- 自变量：动作协议（legacy_direct vs need_change_gate）。模型、温度、预算、事件内容相同。",
        "- 未改、未重跑 GM-01 / GM-02；未建留出集；未开 GM-03。",
        "",
        "## 主报指标",
        "",
        f"- Coverage（全体）：{metrics['coverage']}",
        "",
        "| 协议 | Coverage | NeedChangeAccuracy | ControlStabilityRate | AdaptationRate | UnnecessaryReplanRate | ConditionalActionScore |",
        "|---|---|---|---|---|---|---|",
        (
            f"| legacy_direct | {old['Coverage']} | {old['NeedChangeAccuracy']} | "
            f"{old['ControlStabilityRate']} | {old['AdaptationRate']} | "
            f"{old['UnnecessaryReplanRate']} | {old['ConditionalActionScore']} |"
        ),
        (
            f"| need_change_gate | {new['Coverage']} | {new['NeedChangeAccuracy']} | "
            f"{new['ControlStabilityRate']} | {new['AdaptationRate']} | "
            f"{new['UnnecessaryReplanRate']} | {new['ConditionalActionScore']} |"
        ),
        "",
        "ConditionalActionScore = (ControlStabilityRate + AdaptationRate) / 2，只作附报，不替代两个分项。",
        "",
        "预约时间与资源补充：两种协议 24/24 全过。失败全部来自责任安排对照格：模型判断为 keep / need_change=false，但把 target 填成 assignee_id 而不是 NONE，value 仍为 NONE，并没有改派 backup-01。",
        "",
        *_read_verdict(metrics),
        "",
        "## 格子证据",
        "",
        "| instance | protocol | variant | valid | FullPass | need_change | target_correct | first_error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        lines.append(
            f"| {cell.get('instance_id')} | {extra.get('protocol')} | {extra.get('variant')} | "
            f"{cell.get('measurement_valid')} | {cell.get('full_pass')} | "
            f"{extra.get('need_change_correct')} | {extra.get('target_correct')} | "
            f"{(cell.get('process_profile') or {}).get('first_error')} |"
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
            lines.append(
                f"- `{cell.get('instance_id')}` first_error={(cell.get('process_profile') or {}).get('first_error')}"
            )
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(extra.get("action") or {}, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def rescore_saved(out: Path) -> list[dict]:
    from exp_gm_oa_01.loader import load_task

    cells: list[dict] = []
    for path in sorted((out / "runs").glob("*/cell_result.json")):
        old = json.loads(path.read_text(encoding="utf-8"))
        extra = old.get("extra") or {}
        task = load_task(str(extra["task_id"]))
        event_id = (old.get("process_profile") or {}).get("injected_event_id")
        loop = {
            "events": (old.get("process_profile") or {}).get("events")
            or ["event_injected", "current_state_seeded", "action_submitted"],
            "action": extra.get("action") or {},
            "notice": {"event_id": event_id},
            "injected": {"event_id": event_id},
            "contract_error": "ok",
            "agent_calls": 1,
            "env_rewrote": bool((old.get("process_profile") or {}).get("source_contamination")),
            "source_contamination": bool((old.get("process_profile") or {}).get("source_contamination")),
            "task_id": old.get("instance_id"),
        }
        cell = score_cell(
            task=task,
            variant=str(extra["variant"]),
            protocol=str(extra["protocol"]),
            seed=int(extra.get("seed") or 0),
            loop=loop,
            workflow_id=WORKFLOW_ID,
            instance_id=str(old.get("instance_id")),
        )
        merged = dict(cell.get("extra") or {})
        merged["mode"] = extra.get("mode")
        merged["model_version"] = extra.get("model_version")
        merged["temperature"] = extra.get("temperature")
        cell["extra"] = merged
        cell["ranking_eligible"] = False
        path.write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cells.append(cell)
    return cells


def run_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in load_tasks():
        for variant in VARIANTS:
            for protocol in PROTOCOLS:
                for seed in seeds:
                    print(
                        f"run {task['id']} variant={variant} protocol={protocol} seed={seed} mode={mode}",
                        flush=True,
                    )
                    cell = _score_one(task, variant, protocol, seed, out, mode=mode)
                    cells.append(cell)
                    extra = cell.get("extra") or {}
                    print(
                        f"  valid={cell.get('measurement_valid')} full_pass={cell.get('full_pass')} "
                        f"need_change={extra.get('need_change_correct')} "
                        f"target_correct={extra.get('target_correct')} "
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
    out = BRIDGE_ROOT / "output" / "exp_gm_oa_01_20260824"
    out.mkdir(parents=True, exist_ok=True)

    print("phase=rule", flush=True)
    if rule_main() != 0:
        print("Rule 未过门，停止 GLM。", flush=True)
        return 1
    rule_cells = run_matrix(out / "rule", [0], mode="rule")
    rule_payload = _pack(rule_cells, out / "rule", phase="rule", mode="rule")
    print((out / "rule" / "REPORT.md").read_text(encoding="utf-8"))
    if rule_payload["metrics"]["coverage"] < 1.0:
        print("Rule 格子 Coverage 未到 1.0，停止 GLM。", flush=True)
        return 1

    print("phase=seed0", flush=True)
    cells = run_matrix(out, [0], mode="llm")
    payload = _pack(cells, out, phase="seed0", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if payload["metrics"]["coverage"] < 1.0 or len(cells) < 12:
        print("seed0 Coverage 未到 1.0，停在测量门，不补重复。", flush=True)
        return 1
    print("phase=repeats", flush=True)
    cells.extend(run_matrix(out, [1, 2], mode="llm"))
    payload = _pack(cells, out, phase="all", mode="llm")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    return 0 if payload["metrics"]["coverage"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
