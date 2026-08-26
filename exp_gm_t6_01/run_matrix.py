"""Run the deterministic T6 population approximation calibration matrix."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.eval_mode import capture_eval_mode_evidence
from exp_gm_t6_01.loader import MODES, TRACKS, load_tasks
from exp_gm_t6_01.loop import run_cell
from exp_gm_t6_01.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_t6_01_population"


def _eval_evidence() -> dict[str, Any]:
    ensure_import_paths()
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _cells(
    cells: list[dict[str, Any]], *, mode: str | None = None, track: str | None = None
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for cell in cells:
        context = (cell.get("extra") or {}).get("run_context") or {}
        if mode is not None and context.get("variant") != mode:
            continue
        if track is not None and context.get("track") != track:
            continue
        selected.append(cell)
    return selected


def _pass_rate(cells: list[dict[str, Any]]) -> float | None:
    scored = [cell for cell in cells if cell.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(cell["full_pass"]) for cell in scored) / len(scored), 4)


def _mean(cells: list[dict[str, Any]], key: str) -> float | None:
    values = [
        float((cell.get("extra") or {}).get(key))
        for cell in cells
        if (cell.get("extra") or {}).get(key) is not None
    ]
    return None if not values else round(sum(values) / len(values), 6)


def summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    workflow = summarize_workflow(WORKFLOW_ID, cells)
    pass_by_mode = {mode: _pass_rate(_cells(cells, mode=mode)) for mode in MODES}
    pass_by_track = {track: _pass_rate(_cells(cells, track=track)) for track in TRACKS}
    max_gap = {
        mode: max(
            float((cell.get("extra") or {}).get("max_distribution_error") or 0.0)
            for cell in _cells(cells, mode=mode)
        )
        for mode in MODES
    }
    cost = {mode: _mean(_cells(cells, mode=mode), "operation_units") for mode in MODES}
    individual_cost = cost["individual"]
    cost_ratio = {
        mode: (
            None
            if individual_cost in {None, 0} or cost[mode] is None
            else round(float(cost[mode]) / float(individual_cost), 6)
        )
        for mode in MODES
    }
    gate = "rule_calibration_failed"
    if (
        workflow["requested"] == 18
        and workflow["coverage"] == 1.0
        and pass_by_mode == {"individual": 1.0, "cohort": 1.0, "fast_forward": 1.0}
        and pass_by_track == {"continuous": 1.0, "checkpoint_resume": 1.0}
        and max(max_gap.values()) <= 1e-9
        and cost_ratio["fast_forward"] < cost_ratio["cohort"] < 1.0
    ):
        gate = "rule_calibration_pass"
    return {
        "experiment_id": "EXP-GM-T6-01",
        "phase": "rule_calibration",
        "gate": gate,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "FullPassByMode": pass_by_mode,
        "FullPassByTrack": pass_by_track,
        "MaxRegisteredDistributionGap": max_gap,
        "MeanOperationUnits": cost,
        "OperationCostRatioToIndividual": cost_ratio,
        "claim": (
            "个体/cohort/fast-forward登记矩与检查点恢复校准通过；不含真人或网络结构效度。"
            if gate.endswith("pass")
            else "回到分布Oracle、成本契约或恢复链路修复。"
        ),
    }


def run_rule_matrix(out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for mode in MODES:
            for track in TRACKS:
                instance_id = f"{task['id']}_{mode}_{track}_s0"
                run_dir = out / "runs" / instance_id
                loop = run_cell(task, mode, track, run_dir)
                cell = score_cell(
                    task=task,
                    mode=mode,
                    track=track,
                    seed=0,
                    loop=loop,
                    eval_mode_evidence=evidence,
                )
                (run_dir / "cell_result.json").write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                cells.append(cell)
    report = summarize(cells)
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "GATE.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (out / "REPORT.md").write_text(
        "\n".join(
            [
                "# EXP-GM-T6-01 Rule校准",
                "",
                f"- gate: `{report['gate']}`",
                f"- FullPassByMode: `{report['FullPassByMode']}`",
                f"- MaxRegisteredDistributionGap: `{report['MaxRegisteredDistributionGap']}`",
                f"- OperationCostRatioToIndividual: `{report['OperationCostRatioToIndividual']}`",
                "- ranking_eligible: false",
                "- 结论：只证明登记矩与恢复机制可校准，不代表社会结构或真人长期效度。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=BRIDGE_ROOT / "output" / "exp_gm_t6_01_v1"
    )
    args = parser.parse_args()
    _, report = run_rule_matrix(args.out)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] == "rule_calibration_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
