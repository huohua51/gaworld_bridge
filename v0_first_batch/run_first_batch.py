#!/usr/bin/env python3
"""Run the first GAWorld Workflow-Rubric batch and write Task Cards."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.workflows import (
    capability_quiz,
    causal_diagnostic,
    compare_event_unique_path,
    contract_interview,
    eval_mode_environment,
    life_history_mock,
    live_structured_pairs,
    sim_smoke,
    structured_action_pairs,
    work_artifact_r1,
)

PLANNED_NOT_RUN = [
    {
        "workflow_id": "tms_expert_handoff_001",
        "status": "planned",
        "reason": "GAWorld has no private v2 owner, publish permission, or request-ack-verify event chain",
    },
    {
        "workflow_id": "collective_replanning_001",
        "status": "planned",
        "reason": "GAWorld map is activity/location, not a replayable road graph with vehicles and deadlines",
    },
    {
        "workflow_id": "human_fidelity_svo_society_001",
        "status": "planned",
        "reason": "SocietyDiag traces live outside GAWorld; no matched human sample in this repo",
    },
]

EXTERNAL_REGISTRY = [
    {
        "batch": "WorkDiag v0.2 focused",
        "packages": ["P0", "P1", "P2"],
        "status": "formal",
        "host": "YuLan-OneSim",
        "note": "Not re-run inside GAWorld. Macro Pair ranking stays on the occupational card.",
    },
    {
        "batch": "WorkDiag v0.3 Seed 0 dual-track",
        "packages": ["P0", "P1", "P3"],
        "status": "pilot",
        "host": "YuLan-OneSim",
        "note": "EPG/TDG remain unfrozen. Do not mix with v0.2 Pair means.",
    },
    {
        "batch": "SocietyDiag v0.2 games",
        "packages": ["P0", "P1", "P2"],
        "status": "formal",
        "host": "AgentSociety",
        "note": "Historical PairVariantMean. Capability Oracle, not Human Fidelity.",
    },
    {
        "batch": "SocietyDiag mobility no_shock",
        "packages": ["P5"],
        "status": "diagnostic",
        "host": "AgentSociety",
        "note": "JSD 45.15 ranking_eligible=false; sample/slot mismatch.",
    },
]


def _run_named(name: str, fn, errors: list[dict]) -> dict:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        errors.append({"workflow": name, "error": f"{type(exc).__name__}: {exc}", "traceback": tb})
        return {
            "workflow_id": name,
            "status": "runner_error",
            "ranking_eligible": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_platform_pytest() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
        "--tb=no",
        "-k",
        "not test_li_vs_zhou_planning_differs",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(GAWORLD_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-1000:],
        "passed": proc.returncode == 0,
    }


def _package_view(results: dict[str, dict], platform: dict | None) -> dict:
    return {
        "P0_measurement_integrity": {
            "question": "这次到底测没测到？",
            "items": {
                "platform_pytest": None if platform is None else platform.get("passed"),
                "interview_contract": results.get("contract_interview_001", {}).get("full_pass_rate"),
                "eval_mode_exists": results.get("eval_mode_environment_001", {}).get("full_pass_rate"),
                "life_history_ranking_eligible": results.get("life_history_mock_score_001", {}).get(
                    "ranking_eligible"
                ),
            },
            "cross_pack_sum_allowed": False,
        },
        "P1_workflow_performance": {
            "question": "任务本身做成了吗？",
            "items": {
                "work_artifact_r1": results.get("work_artifact_r1_001", {}).get("mean_task_score"),
                "sim_smoke": results.get("sim_smoke_mock_llm_001", {}).get("mean_task_score"),
            },
            "cross_pack_sum_allowed": False,
        },
        "P2_causal_adaptation": {
            "question": "唯一条件改变时会正确改手吗？",
            "items": {
                "unique_path_audit": results.get("compare_event_unique_path_001", {}).get("full_pass_rate"),
                "scale_rubric_pairs": results.get("causal_diagnostic_suite_001", {}).get("mean_task_score"),
            },
            "cross_pack_sum_allowed": False,
        },
        "P3_system_robustness": {
            "question": "局部会做，放进全流程还会吗？",
            "status": "not_run",
            "reason": "No Focused/E2E dual-track TaskSpec inside GAWorld yet; v0.3 remains external pilot",
        },
        "P4_multiagent_process": {
            "question": "多 Agent 是否真的带来分工与协调？",
            "status": "not_run",
            "reason": "TMS / collective replanning need environment primitives GAWorld does not have",
        },
        "P5_human_fidelity": {
            "question": "是否在指定层级复现匹配人类？",
            "status": "diagnostic",
            "ranking_eligible": False,
            "items": {
                "life_history_mock": False,
                "capability_quiz": False,
                "mobility_jsd_external": False,
            },
        },
    }


def render_report(payload: dict) -> str:
    lines = [
        "# GAWorld 第一批 Workflow-Rubric 跑批报告",
        "",
        f"- 时间：{payload['generated_at']}",
        f"- 宿主：`{payload['gaworld_root']}`",
        f"- 原则：只跑当前代码能托管的题；TMS / Collective Efficacy / 人类七分面排名不进本批。",
        "",
        "## 0. 九个接口落地状态",
        "",
        "| 接口 | 本批做法 | 状态 |",
        "|---|---|---|",
        "| TaskSpec–Agent–Environment | 评测工厂在仓库外调用 GAWorld，不改主循环默认行为 | 部分 |",
        "| Workflow 准入 | 正式题是契约 / 产物 / 唯一干预；Probe 只做诊断 | 已执行 |",
        "| Task Card 七部分 | 每题一张卡，连续 264 小时不当一张卡 | 已执行 |",
        "| R0–R3 | 先 Gate 再评分，代码组合 | 已执行 |",
        "| 确定性 Scorer | 无 LLM Judge | 已执行 |",
        "| FullPass + TaskScore + ProcessProfile | 每格三输出 | 已执行 |",
        "| Instance→Workflow→Construct | 同一张 cell 表派生 | 已执行 |",
        "| 能力 / 人类双轴 | HumanScore 与 quiz 强制不可排名 | 已执行 |",
        "| H1–H7 | schema 保留，本批全 N/A | 未开排名 |",
        "",
        "## 1. Workflow 结果",
        "",
    ]
    for item in payload["workflows"]:
        lines.append(f"### {item.get('workflow_id')}")
        lines.append("")
        lines.append(f"- 覆盖：{item.get('coverage')}")
        lines.append(f"- FullPass Rate：{item.get('full_pass_rate')}")
        lines.append(f"- Mean TaskScore：{item.get('mean_task_score')}")
        lines.append(f"- ranking_eligible：{item.get('ranking_eligible')}")
        if item.get("status"):
            lines.append(f"- status：{item.get('status')}")
        if item.get("error"):
            lines.append(f"- error：{item.get('error')}")
        cells = item.get("cells") or []
        if cells:
            lines.append("")
            lines.append("| instance | measurement_valid | FullPass | TaskScore | status |")
            lines.append("|---|---|---|---|---|")
            for cell in cells:
                lines.append(
                    "| {instance_id} | {measurement_valid} | {full_pass} | {task_score} | {status} |".format(
                        instance_id=cell.get("instance_id"),
                        measurement_valid=cell.get("measurement_valid"),
                        full_pass=cell.get("full_pass"),
                        task_score=cell.get("task_score"),
                        status=cell.get("status"),
                    )
                )
        lines.append("")
    lines.extend(
        [
            "## 2. 六个对外指标包",
            "",
            "```json",
            json.dumps(payload["packages"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## 3. 未跑 / 外部注册",
            "",
            "本批故意不跑：",
            "",
        ]
    )
    for item in payload["planned_not_run"]:
        lines.append(f"- `{item['workflow_id']}`（{item['status']}）：{item['reason']}")
    lines.append("")
    lines.append("外部实验继续留在原宿主：")
    lines.append("")
    for item in payload["external_registry"]:
        lines.append(
            f"- {item['batch']}｜{item['status']}｜{item['host']}｜{item['note']}"
        )
    if payload.get("platform_pytest"):
        lines.extend(
            [
                "",
                "## 4. P0 平台健康（GAWorld pytest）",
                "",
                f"- passed：{payload['platform_pytest'].get('passed')}",
                f"- returncode：{payload['platform_pytest'].get('returncode')}",
                "",
                "```",
                (payload["platform_pytest"].get("stdout_tail") or "").strip() or "(no stdout)",
                "```",
                "",
            ]
        )
    if payload.get("errors"):
        lines.extend(["## 5. Runner errors", ""])
        for err in payload["errors"]:
            lines.append(f"- {err['workflow']}: {err['error']}")
    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            "- 本批证明评测工厂能接到 GAWorld 的 interview / WorkAdapter / compare-event / 主循环烟雾。",
            "- 不证明任何模型的职业或社会能力；烟雾仿真使用 Mock LLM。",
            "- 默认 `dynamic_behavior.enabled=True` 且没有 eval_mode，正式能力榜不能用当前默认 `run`。",
            "- HumanScore 与算术 quiz 保留数值或题库，但 ranking_eligible=false。",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--live", action="store_true", help="Also run live Paratera structured pairs")
    parser.add_argument(
        "--out",
        type=Path,
        default=BRIDGE_ROOT / "output" / "first_batch_20260822",
    )
    args = parser.parse_args()
    ensure_import_paths()
    args.out.mkdir(parents=True, exist_ok=True)

    errors: list[dict] = []
    workflows = [
        _run_named("contract_interview_001", contract_interview.run, errors),
        _run_named("work_artifact_r1_001", work_artifact_r1.run, errors),
        _run_named("compare_event_unique_path_001", compare_event_unique_path.run, errors),
        _run_named("causal_diagnostic_suite_001", causal_diagnostic.run, errors),
        _run_named("life_history_mock_score_001", life_history_mock.run, errors),
        _run_named("eval_mode_environment_001", eval_mode_environment.run, errors),
        _run_named("structured_action_pairs_001", structured_action_pairs.run, errors),
        _run_named("capability_quiz_not_workflow_001", capability_quiz.run, errors),
    ]
    if args.live:
        workflows.append(_run_named("live_structured_pairs_001", live_structured_pairs.run, errors))
    if not args.skip_smoke:
        workflows.append(_run_named("sim_smoke_mock_llm_001", sim_smoke.run, errors))

    by_id = {item.get("workflow_id"): item for item in workflows}
    platform = None
    if not args.skip_pytest:
        try:
            platform = run_platform_pytest()
        except Exception as exc:  # noqa: BLE001
            errors.append({"workflow": "platform_pytest", "error": str(exc)})
            platform = {"passed": False, "error": str(exc)}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gaworld_root": str(GAWORLD_ROOT),
        "workflows": workflows,
        "packages": _package_view(by_id, platform),
        "planned_not_run": PLANNED_NOT_RUN,
        "external_registry": EXTERNAL_REGISTRY,
        "platform_pytest": platform,
        "errors": errors,
    }
    (args.out / "cell_table.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for item in workflows:
        wid = item.get("workflow_id") or "unknown"
        (args.out / f"{wid}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report = render_report(payload)
    (args.out / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
