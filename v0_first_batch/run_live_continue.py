#!/usr/bin/env python3
"""Continue the 2026-08-23 live run: score the finished city sim, then live WorkAdapter."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.workflows import live_city_run, live_work_artifact


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render(out: Path, city: dict, work: dict) -> str:
    lines = [
        "# 真模型第三拍：eval_mode 城市日已完成，并补了 WorkAdapter 真产物",
        "",
        f"- 时间：{datetime.now(timezone.utc).isoformat()}",
        f"- 通道：Paratera `GLM-4-Flash`",
        f"- 目录：`{out}`",
        "",
        "## 已完成",
        "",
        "| 轨 | 结果 | 能说什么 |",
        "|---|---|---|",
        "| LLM ping / 结构化 Pair × 3 | 覆盖 1.0，Mean TaskScore 0.5，FullPass Rate 0 | 能力 Oracle；保留工资三次锁死 |",
        "| 真访谈 JSON 契约 | Agent 4，FullPass=1 | 只证明可测量，不证明诚实 |",
        "| eval_mode 1 日 × Agent 4/5 | `{city_status}` | 城市 run 的 P0/R1，无 Oracle，不可排名 |".format(
            city_status=f"measurement_valid={city.get('measurement_valid')} diaries+state 齐"
        ),
        "| 真模型 WorkAdapter R1 | `{work_status}` | 合法产物门，不是 Task Competence |".format(
            work_status=f"coverage={work.get('coverage')} full_pass_rate={work.get('full_pass_rate')}"
        ),
        "",
        "### eval_mode 城市日",
        "",
        f"- coverage：{city.get('coverage')}",
        f"- FullPass Rate：{city.get('full_pass_rate')}（本轨没有 R2 Oracle，不得当能力分）",
        f"- ranking_eligible：{city.get('ranking_eligible')}",
        f"- note：{city.get('note')}",
        "",
    ]
    for cell in city.get("cells") or []:
        extra = cell.get("extra") or {}
        attr = extra.get("attribution") or {}
        lines.extend(
            [
                f"- instance：`{cell.get('instance_id')}` status=`{cell.get('status')}`",
                f"- 日记字数：{extra.get('diary_chars')}",
                f"- state 行数：{extra.get('state_rows')}",
                f"- 归因：{json.dumps(attr, ensure_ascii=False)}",
                "",
            ]
        )
        lines.append("| gate | passed | detail |")
        lines.append("|---|---|---|")
        for gate in cell.get("gates") or []:
            lines.append(
                f"| {gate.get('gate_id')} | {gate.get('passed')} | {gate.get('detail')} |"
            )
        lines.append("")
    lines.extend(
        [
            "### WorkAdapter 真产物",
            "",
            f"- coverage：{work.get('coverage')}",
            f"- FullPass Rate：{work.get('full_pass_rate')}",
            f"- Mean TaskScore：{work.get('mean_task_score')}",
            f"- note：{work.get('note')}",
            "",
            "| instance | FullPass | TaskScore | status | 产物 |",
            "|---|---|---|---|---|",
        ]
    )
    for cell in work.get("cells") or []:
        extra = cell.get("extra") or {}
        paths = extra.get("artifact_paths") or []
        lines.append(
            "| {instance_id} | {full_pass} | {task_score} | {status} | {paths} |".format(
                instance_id=cell.get("instance_id"),
                full_pass=cell.get("full_pass"),
                task_score=cell.get("task_score"),
                status=cell.get("status"),
                paths=", ".join(os.path.basename(p) for p in paths) or extra.get("error") or "",
            )
        )
    lines.extend(
        [
            "",
            "## 仍未做（按文档验收，不要写成已完成）",
            "",
            "- 输入层 `intervention_audit.json`（requested / applied / 未登记外生 diff）",
            "- 七文件最小证据包（现在只有 `run_manifest.json` + 工厂 cell）",
            "- `environment_overrides.jsonl` 与三归因量",
            "- `compare-event` / `personal-what-if` 真模型双轨（会再开两整天仿真，本拍没开）",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    os.environ.setdefault("GAWORLD_LLM_PROVIDER", "paratera_glm")
    out = BRIDGE_ROOT / "output" / "live_run_20260823"
    out.mkdir(parents=True, exist_ok=True)
    print("scoring finished eval_mode city run...")
    city = live_city_run.run(out / "sim")
    _write(out / "live_eval_mode_city_run_001.json", city)
    print(
        "city coverage={coverage} full_pass_rate={full_pass_rate} ranking_eligible={ranking_eligible}".format(
            **{k: city.get(k) for k in ("coverage", "full_pass_rate", "ranking_eligible")}
        )
    )
    print("running live WorkAdapter R1...")
    work = live_work_artifact.run(out / "work")
    _write(out / "live_work_artifact_r1_001.json", work)
    print(
        "work coverage={coverage} full_pass_rate={full_pass_rate} mean_task_score={mean_task_score}".format(
            **{k: work.get(k) for k in ("coverage", "full_pass_rate", "mean_task_score")}
        )
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "city": city,
        "work": work,
    }
    _write(out / "continue_cell_table.json", payload)
    report = _render(out, city, work)
    (out / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
