"""Run the deterministic T5 urban-policy calibration matrix."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.eval_mode import capture_eval_mode_evidence
from exp_gm_t5_01.loader import CONDITIONS, TRACKS, load_tasks
from exp_gm_t5_01.loop import run_cell
from exp_gm_t5_01.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

WORKFLOW_ID = "exp_gm_t5_01_policy"


def _eval_evidence() -> dict[str, Any]:
    ensure_import_paths()
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _cells(
    cells: list[dict[str, Any]], track: str, condition: str
) -> list[dict[str, Any]]:
    return [
        cell
        for cell in cells
        if (cell.get("extra") or {}).get("run_context", {}).get("track") == track
        and (cell.get("extra") or {}).get("run_context", {}).get("variant") == condition
    ]


def _rate(cells: list[dict[str, Any]]) -> float | None:
    scored = [cell for cell in cells if cell.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(cell["full_pass"]) for cell in scored) / len(scored), 4)


def _mean_change(cells: list[dict[str, Any]]) -> float | None:
    valid = [cell for cell in cells if cell.get("measurement_valid")]
    if not valid:
        return None
    return round(
        sum(
            float((cell.get("extra") or {}).get("behavior_change_rate") or 0.0)
            for cell in valid
        )
        / len(valid),
        4,
    )


def summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    workflow = summarize_workflow(WORKFLOW_ID, cells)
    full_pass = {
        track: {
            condition: _rate(_cells(cells, track, condition))
            for condition in CONDITIONS
        }
        for track in TRACKS
    }
    full_change = {
        condition: _mean_change(_cells(cells, "full", condition))
        for condition in CONDITIONS
    }
    real = full_change["real_policy"]
    baseline = full_change["no_policy"]
    placebo = full_change["placebo_policy"]
    treatment_effect = (
        None if real is None or baseline is None else round(real - baseline, 4)
    )
    placebo_effect = (
        None if placebo is None or baseline is None else round(placebo - baseline, 4)
    )
    invalid_disconnects = sum(
        1
        for condition in ("real_policy", "placebo_policy")
        for cell in _cells(cells, "disconnect_policy", condition)
        if not cell.get("measurement_valid")
    )
    gate = "rule_calibration_failed"
    if (
        workflow["requested"] == 18
        and full_pass["full"]
        == {"no_policy": 1.0, "real_policy": 1.0, "placebo_policy": 1.0}
        and full_pass["disconnect_policy"]
        == {"no_policy": 1.0, "real_policy": None, "placebo_policy": None}
        and treatment_effect == 0.5
        and placebo_effect == 0.0
        and invalid_disconnects == 6
    ):
        gate = "rule_calibration_pass"
    return {
        "experiment_id": "EXP-GM-T5-01",
        "phase": "rule_calibration",
        "gate": gate,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "FullPassByCondition": full_pass,
        "BehaviorChangeRate": full_change,
        "TreatmentEffect": treatment_effect,
        "PlaceboEffect": placebo_effect,
        "DisconnectedTreatmentCellsRejectedAtR0": invalid_disconnects,
        "claim": (
            "政策因果链与安慰剂/R0负控校准通过；尚未运行模型或真人效度比较。"
            if gate.endswith("pass")
            else "回到R0或政策响应Oracle修复。"
        ),
    }


def run_rule_matrix(out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for condition in CONDITIONS:
            for track in TRACKS:
                instance_id = f"{task['id']}_{condition}_{track}_s0"
                run_dir = out / "runs" / instance_id
                loop = run_cell(task, condition, track, run_dir)
                cell = score_cell(
                    task=task,
                    condition=condition,
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
                "# EXP-GM-T5-01 Rule校准",
                "",
                f"- gate: `{report['gate']}`",
                f"- FullPassByCondition: `{report['FullPassByCondition']}`",
                f"- TreatmentEffect: {report['TreatmentEffect']}",
                f"- PlaceboEffect: {report['PlaceboEffect']}",
                "- ranking_eligible: false",
                "- 结论：只证明政策功能证据链和Scorer正负控可用，不代表真实政策效果。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=BRIDGE_ROOT / "output" / "exp_gm_t5_01_v1"
    )
    args = parser.parse_args()
    _, report = run_rule_matrix(args.out)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] == "rule_calibration_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
