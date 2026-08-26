"""Run the deterministic T4-v2 platform and scorer calibration matrix."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.eval_mode import capture_eval_mode_evidence
from exp_gm_t4_02.loader import TRACKS, VARIANTS, load_tasks
from exp_gm_t4_02.loop import run_cell
from exp_gm_t4_02.scorer import WORKFLOW_ID, score_cell
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


def _valid(
    cells: list[dict[str, Any]], track: str, variant: str | None = None
) -> list[dict[str, Any]]:
    return [
        cell
        for cell in cells
        if cell.get("measurement_valid")
        and _context(cell).get("track") == track
        and (variant is None or _context(cell).get("variant") == variant)
    ]


def _rate(cells: list[dict[str, Any]]) -> float | None:
    scored = [cell for cell in cells if cell.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(cell["full_pass"]) for cell in scored) / len(scored), 4)


def _strict_pair(cells: list[dict[str, Any]], track: str) -> float | None:
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for cell in _valid(cells, track):
        context = _context(cell)
        groups.setdefault(str(context.get("task_id")), {})[
            str(context.get("variant"))
        ] = cell
    pairs = [group for group in groups.values() if set(group) == set(VARIANTS)]
    if not pairs:
        return None
    passed = sum(
        group["control"].get("full_pass") == 1
        and group["intervention"].get("full_pass") == 1
        for group in pairs
    )
    return round(passed / len(pairs), 4)


def summarize(cells: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = summarize_workflow(WORKFLOW_ID, cells)["coverage"]
    fullpass = {track: _rate(_valid(cells, track)) for track in TRACKS}
    by_variant = {
        track: {variant: _rate(_valid(cells, track, variant)) for variant in VARIANTS}
        for track in TRACKS
    }
    full_intervention = by_variant["full"]["intervention"]
    remove_intervention = by_variant["remove_bridge"]["intervention"]
    drop_intervention = by_variant["drop_bridge"]["intervention"]
    remove_value = (
        None
        if full_intervention is None or remove_intervention is None
        else round(full_intervention - remove_intervention, 4)
    )
    drop_value = (
        None
        if full_intervention is None or drop_intervention is None
        else round(full_intervention - drop_intervention, 4)
    )
    calibrated = (
        len(cells) == 18
        and coverage == 1.0
        and by_variant["full"] == {"control": 1.0, "intervention": 1.0}
        and by_variant["remove_bridge"]
        == {"control": 1.0, "intervention": 0.0}
        and by_variant["drop_bridge"]
        == {"control": 1.0, "intervention": 0.0}
    )
    return {
        "experiment_id": "EXP-GM-T4-02",
        "phase": "rule_calibration",
        "gate": "rule_calibration_pass" if calibrated else "rule_calibration_failed",
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": coverage,
        "FullPass": fullpass,
        "FullPassByVariant": by_variant,
        "StrictPair": {track: _strict_pair(cells, track) for track in TRACKS},
        "CommunicationValueRemoveBridge": remove_value,
        "CommunicationValueDropBridge": drop_value,
        "claim": (
            "Registered-transport platform and scorer controls calibrated; "
            "no live-model capability claim."
            if calibrated
            else "Return to R0/R1 calibration before model execution."
        ),
    }


def run_rule_matrix(out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                instance_id = f"{task['id']}_{variant}_{track}_s0"
                run_dir = out / "runs" / instance_id
                loop = run_cell(task, variant, track, run_dir)
                cell = score_cell(
                    task=task,
                    variant=variant,
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
                "# EXP-GM-T4-02 rule calibration",
                "",
                f"- gate: `{report['gate']}`",
                f"- coverage: {report['coverage']}",
                f"- FullPassByVariant: `{report['FullPassByVariant']}`",
                f"- remove-bridge value: {report['CommunicationValueRemoveBridge']}",
                f"- drop-bridge value: {report['CommunicationValueDropBridge']}",
                "- ranking_eligible: false",
                "- conclusion: platform/scorer calibration only; no live-model claim.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=BRIDGE_ROOT / "output" / "exp_gm_t4_02_v1"
    )
    args = parser.parse_args()
    _, report = run_rule_matrix(args.out)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] == "rule_calibration_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
