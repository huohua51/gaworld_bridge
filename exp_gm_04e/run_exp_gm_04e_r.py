#!/usr/bin/env python3
"""EXP-GM-04e-R: evidence-bound Reviewer only. Stop if development gates fail."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from exp_gm_04e.loop import run_reviewer_cell
from exp_gm_04e.roles import evidence_prompt, facts_for, legacy_prompt, parse_review, rule_reviewer
from exp_gm_04e.scoring import grounding_rate, mean_calls, parse_rate, r0_ok, rate
from exp_gm_04e.tasks import TASKS
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import CriterionResult, GateResult, compose, summarize_workflow

WORKFLOW_ID = "exp_gm_04e_r_reviewer_only"
PROTOCOLS = ("legacy", "evidence_bound")
VARIANTS = ("control", "intervention")


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


def _reviewer_fn(task: dict, protocol: str, mode: str):
    if mode == "rule":
        def _fn(source, private, extra):
            return rule_reviewer(task, source, private, protocol=protocol)

        return _fn

    def _fn(source, private, extra):
        if protocol == "evidence_bound":
            prompt = evidence_prompt(source, facts_for(task, source), private, extra=extra)
        else:
            prompt = legacy_prompt(source, private, extra=extra)
        try:
            return parse_review(_llm(prompt))
        except (ValueError, json.JSONDecodeError):
            return {}

    return _fn


def _score_cell(task: dict, variant: str, protocol: str, seed: int, out_root: Path, *, mode: str) -> dict:
    ensure_import_paths()
    from config import CONFIG
    from gaworld.eval_mode import apply_eval_mode_runtime

    cfg = CONFIG
    cfg.setdefault("eval_mode", {})
    cfg["eval_mode"]["enabled"] = True
    apply_eval_mode_runtime(cfg)

    instance_id = f"{task['id']}_{variant}_{protocol}_s{seed}"
    run_dir = out_root / "runs" / instance_id
    loop = run_reviewer_cell(
        task=task,
        variant=variant,
        protocol=protocol,
        task_id=instance_id,
        out_dir=run_dir,
        reviewer_fn=_reviewer_fn(task, protocol, mode),
    )
    r0, r0_detail = r0_ok(loop)
    parseable = bool((loop.get("review") or {}).get("decision") in {"approve", "revise"})
    grounded = bool(loop.get("grounded"))
    fp = bool(loop.get("false_positive_revision"))
    true_rev = bool(loop.get("true_revision"))
    expected_ok = (variant == "control" and not fp) or (variant == "intervention" and true_rev)
    cell = compose(
        workflow_id=WORKFLOW_ID,
        instance_id=instance_id,
        measurement_gates=[
            GateResult("execution_valid", r0, layer="R0", detail=r0_detail),
            GateResult("eval_mode_on", True, layer="R0"),
            GateResult("fields_extractable", True, layer="R0", detail="reviewer-only cell executed"),
        ],
        artifact_gates=[
            GateResult("reviewer_only", True, layer="R1", detail="executor not run"),
        ],
        criteria=[
            CriterionResult(
                criterion_id="review_correct",
                layer="R2",
                scorer="reviewer_oracle",
                evaluable=True,
                score=1.0 if expected_ok else 0.0,
                passed=expected_ok,
                critical=True,
            ),
        ],
        process_profile={"first_error": loop.get("first_error"), "events": loop.get("events")},
        extra={
            "task_id": task["id"],
            "variant": variant,
            "protocol": protocol,
            "seed": seed,
            "mode": mode,
            "split": "development",
            "reviewer_calls": loop.get("reviewer_calls"),
            "false_positive_revision": fp,
            "true_revision": true_rev,
            "grounded": grounded,
            "review_parseable": parseable,
            "review": loop.get("review"),
            "verify": loop.get("verify"),
            "ranking_note": "pilot, not a leaderboard",
        },
    )
    cell["ranking_eligible"] = False
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cell


def _pack(cells: list[dict], out: Path, *, phase: str) -> dict:
    summary = summarize_workflow(WORKFLOW_ID, cells)
    summary["ranking_eligible"] = False
    fp_old = rate(cells, "false_positive_revision", variant="control", protocol="legacy")
    fp_new = rate(cells, "false_positive_revision", variant="control", protocol="evidence_bound")
    tr_old = rate(cells, "true_revision", variant="intervention", protocol="legacy")
    tr_new = rate(cells, "true_revision", variant="intervention", protocol="evidence_bound")
    ground = grounding_rate(cells, protocol="evidence_bound")
    parse_old = parse_rate(cells, protocol="legacy")
    parse_new = parse_rate(cells, protocol="evidence_bound")
    calls_old = mean_calls(cells, protocol="legacy")
    calls_new = mean_calls(cells, protocol="evidence_bound")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_id": "EXP-GM-04e",
        "phase": "04e-R",
        "ranking_eligible": False,
        "held_out_run": False,
        "summary": summary,
        "false_positive_revision_rate_old": fp_old,
        "false_positive_revision_rate_new": fp_new,
        "true_revision_rate_old": tr_old,
        "true_revision_rate_new": tr_new,
        "evidence_grounding_rate": ground,
        "parse_rate_old": parse_old,
        "parse_rate_new": parse_new,
        "mean_reviewer_calls_old": calls_old,
        "mean_reviewer_calls_new": calls_new,
        "advance_to_04e_e": bool(
            fp_old is not None
            and fp_new is not None
            and tr_old is not None
            and tr_new is not None
            and ground == 1.0
            and parse_new == 1.0
            and parse_old == 1.0
            and fp_new < fp_old
            and tr_new >= tr_old
            and summary.get("coverage") == 1.0
        ),
    }
    (out / "cell_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        "# EXP-GM-04e-R Evidence-bound Reviewer",
        "",
        f"- 时间：{payload['generated_at']}",
        "- 阶段：04e-R，只测 Reviewer，不跑 Executor",
        "- 开发集三题；留出题未触碰",
        "",
        "## 主结果",
        "",
        f"- requested：{summary['requested']}",
        f"- measurement_valid：{summary['measurement_valid']}",
        f"- FalsePositiveRevisionRate 旧：{fp_old} 新：{fp_new}",
        f"- TrueRevisionRate 旧：{tr_old} 新：{tr_new}",
        f"- EvidenceGroundingRate：{ground}",
        f"- 可解析率 旧：{parse_old} 新：{parse_new}",
        f"- 人均 Reviewer 调用 旧：{calls_old} 新：{calls_new}",
        f"- 进入 04e-E：{payload['advance_to_04e_e']}",
        "",
        "## 决策",
        "",
    ]
    if payload["advance_to_04e_e"]:
        report.append("开发集 Reviewer 过门。可以进入 04e-E。")
    else:
        report.append("开发集 Reviewer 未过门。停止，不跑 Executor，不跑留出题。")
    report += [
        "",
        "| instance | protocol | variant | valid | FP | true_rev | grounded | calls | first_error |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for cell in summary["cells"]:
        extra = cell.get("extra") or {}
        report.append(
            f"| {cell.get('instance_id')} | {extra.get('protocol')} | {extra.get('variant')} | "
            f"{cell.get('measurement_valid')} | {extra.get('false_positive_revision')} | "
            f"{extra.get('true_revision')} | {extra.get('grounded')} | {extra.get('reviewer_calls')} | "
            f"{(cell.get('process_profile') or {}).get('first_error')} |"
        )
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return payload


def run_matrix(out: Path, seeds: list[int], *, mode: str) -> list[dict]:
    cells: list[dict] = []
    for task in TASKS:
        for protocol in PROTOCOLS:
            for variant in VARIANTS:
                for seed in seeds:
                    print(
                        f"run {task['id']} protocol={protocol} variant={variant} seed={seed} mode={mode}",
                        flush=True,
                    )
                    cell = _score_cell(task, variant, protocol, seed, out, mode=mode)
                    cells.append(cell)
                    extra = cell.get("extra") or {}
                    print(
                        f"  valid={cell.get('measurement_valid')} fp={extra.get('false_positive_revision')} "
                        f"true_rev={extra.get('true_revision')} grounded={extra.get('grounded')} "
                        f"first_error={(cell.get('process_profile') or {}).get('first_error')}",
                        flush=True,
                    )
    return cells


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    _pin_glm()
    out = BRIDGE_ROOT / "output" / "exp_gm_04e_r_20260824"
    out.mkdir(parents=True, exist_ok=True)
    cells = run_matrix(out, [0, 1, 2], mode="llm")
    payload = _pack(cells, out, phase="04e-R")
    print((out / "REPORT.md").read_text(encoding="utf-8"))
    if not payload["advance_to_04e_e"]:
        print("04e-R 未过门，停止。", flush=True)
        return 1
    print("04e-R 过门。下一步才是 04e-E。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
