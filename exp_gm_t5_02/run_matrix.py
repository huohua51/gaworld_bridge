"""Run the deterministic T5-v2 rule calibration matrix."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.eval_mode import capture_eval_mode_evidence
from exp_gm_t5_02.loader import POLICY_STATES, TRACKS, load_tasks
from exp_gm_t5_02.loop import run_cell
from exp_gm_t5_02.scorer import WORKFLOW_ID, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow


def _eval_evidence() -> dict[str, Any]:
    ensure_import_paths()
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _context(cell: dict[str, Any]) -> dict[str, Any]:
    return (cell.get("extra") or {}).get("run_context") or {}


def _cells(
    cells: list[dict[str, Any]], track: str, policy_state: str
) -> list[dict[str, Any]]:
    return [
        cell
        for cell in cells
        if _context(cell).get("track") == track
        and _context(cell).get("variant") == policy_state
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
        sum(float(cell["extra"]["behavior_change_rate"]) for cell in valid)
        / len(valid),
        4,
    )


def summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    workflow = summarize_workflow(WORKFLOW_ID, cells)
    full_pass = {
        track: {
            state: _rate(_cells(cells, track, state)) for state in POLICY_STATES
        }
        for track in TRACKS
    }
    change = {
        state: _mean_change(_cells(cells, "full", state))
        for state in POLICY_STATES
    }
    binding = change["binding"]
    absence = change["absence"]
    nonbinding = change["nonbinding"]
    binding_minus_absence = (
        None if binding is None or absence is None else round(binding - absence, 4)
    )
    binding_minus_nonbinding = (
        None
        if binding is None or nonbinding is None
        else round(binding - nonbinding, 4)
    )
    nonbinding_minus_absence = (
        None
        if nonbinding is None or absence is None
        else round(nonbinding - absence, 4)
    )
    invalid_disconnects = sum(
        1
        for state in ("binding", "nonbinding")
        for cell in _cells(cells, "disconnect_policy", state)
        if not cell.get("measurement_valid")
    )
    calibrated = (
        workflow["requested"] == 18
        and full_pass["full"]
        == {"absence": 1.0, "binding": 1.0, "nonbinding": 1.0}
        and full_pass["disconnect_policy"]
        == {"absence": 1.0, "binding": None, "nonbinding": None}
        and change == {"absence": 0.0, "binding": 0.5, "nonbinding": 0.0}
        and invalid_disconnects == 6
    )
    return {
        "experiment_id": "EXP-GM-T5-02",
        "phase": "rule_calibration",
        "gate": "rule_calibration_pass" if calibrated else "rule_calibration_failed",
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "FullPassByPolicyState": full_pass,
        "BehaviorChangeRate": change,
        "BindingMinusAbsence": binding_minus_absence,
        "BindingMinusNonbinding": binding_minus_nonbinding,
        "NonbindingMinusAbsence": nonbinding_minus_absence,
        "DisconnectedTreatmentCellsRejectedAtR0": invalid_disconnects,
        "claim": (
            "Explicit policy semantics and causal controls calibrated; no live claim."
            if calibrated
            else "Return to R0/R1 policy-semantics calibration."
        ),
    }


def run_rule_matrix(out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for state in POLICY_STATES:
            for track in TRACKS:
                run_id = f"{task['id']}_{state}_{track}_s0"
                run_dir = out / "runs" / run_id
                loop = run_cell(task, state, track, run_dir)
                cell = score_cell(
                    task=task,
                    policy_state=state,
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
                "# EXP-GM-T5-02 rule calibration",
                "",
                f"- gate: `{report['gate']}`",
                f"- FullPass: `{report['FullPassByPolicyState']}`",
                f"- behavior change: `{report['BehaviorChangeRate']}`",
                f"- binding-minus-nonbinding: {report['BindingMinusNonbinding']}",
                "- ranking_eligible: false",
                "- conclusion: platform/scorer calibration only; no live claim.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=BRIDGE_ROOT / "output" / "exp_gm_t5_02_v1"
    )
    args = parser.parse_args()
    _, report = run_rule_matrix(args.out)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] == "rule_calibration_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
