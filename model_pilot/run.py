"""Run T4/T5 seed-0 model pilots with explicit live-call permission."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.eval_mode import capture_eval_mode_evidence
from benchmark_core.model_runner import (
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from exp_gm_t4_01.loader import TRACKS as T4_TRACKS
from exp_gm_t4_01.loader import VARIANTS as T4_VARIANTS
from exp_gm_t4_01.loader import load_tasks as load_t4_tasks
from exp_gm_t5_01.loader import CONDITIONS as T5_CONDITIONS
from exp_gm_t5_01.loader import TRACKS as T5_TRACKS
from exp_gm_t5_01.loader import load_tasks as load_t5_tasks
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.t4 import run_cell as run_t4_cell
from model_pilot.t4_scorer import score_cell as score_t4_cell
from model_pilot.t5 import run_cell as run_t5_cell
from model_pilot.t5_scorer import score_cell as score_t5_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow


def _eval_evidence() -> dict[str, Any]:
    ensure_import_paths()
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _write_cell(run_dir: Path, cell: dict[str, Any]) -> None:
    (run_dir / "cell_result.json").write_text(
        json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _rate(cells: list[dict[str, Any]]) -> float | None:
    scored = [cell for cell in cells if cell.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(cell["full_pass"]) for cell in scored) / len(scored), 4)


def _context(cell: dict[str, Any]) -> dict[str, Any]:
    return (cell.get("extra") or {}).get("run_context") or {}


def _model_contract_rate(cells: list[dict[str, Any]]) -> float:
    gates = [
        gate
        for cell in cells
        for gate in cell.get("gates") or []
        if gate.get("gate_id") == "model_responses_structured"
    ]
    return (
        0.0
        if not gates
        else round(sum(bool(gate["passed"]) for gate in gates) / len(gates), 4)
    )


def _write_experiment_report(
    out: Path, cells: list[dict[str, Any]], report: dict[str, Any]
) -> None:
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "GATE.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def run_t4_matrix(
    out: Path,
    client: ModelClient,
    budget: ModelCallBudget,
    *,
    temperature: float,
    allow_live_model: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    evidence = _eval_evidence()
    start_calls = budget.snapshot()["calls_used"]
    cells: list[dict[str, Any]] = []
    for task in load_t4_tasks():
        for variant in T4_VARIANTS:
            for track in T4_TRACKS:
                run_id = f"model_{task['id']}_{variant}_{track}_s0"
                run_dir = out / "runs" / run_id
                runner = RecordedModelRunner(
                    run_dir / "model_trace.jsonl",
                    client,
                    budget,
                    temperature=temperature,
                    allow_live_model=allow_live_model,
                    run_id=run_id,
                )
                loop = run_t4_cell(task, variant, track, run_dir, runner)
                cell = score_t4_cell(
                    task=task,
                    variant=variant,
                    track=track,
                    seed=0,
                    loop=loop,
                    eval_mode_evidence=evidence,
                )
                _write_cell(run_dir, cell)
                cells.append(cell)
    by_track = {
        track: {
            variant: _rate(
                [
                    cell
                    for cell in cells
                    if _context(cell).get("track") == track
                    and _context(cell).get("variant") == variant
                ]
            )
            for variant in T4_VARIANTS
        }
        for track in T4_TRACKS
    }
    workflow = summarize_workflow("model_pilot_t4_v1", cells)
    calls = budget.snapshot()["calls_used"] - start_calls
    calibration_pass = (
        len(cells) == 18
        and by_track["full"] == {"control": 1.0, "intervention": 1.0}
        and by_track["remove_bridge"] == {"control": 1.0, "intervention": 0.0}
        and by_track["drop_bridge"] == {"control": 1.0, "intervention": 0.0}
        and _model_contract_rate(cells) == 1.0
    )
    report = {
        "experiment_id": "MODEL-PILOT-T4-v1",
        "base_release": "benchmark-v1.1-rule",
        "phase": "model_seed0_pilot",
        "offline_fixture_calibration_pass": calibration_pass
        if not client.info.live
        else None,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "model_calls": calls,
        "model_contract_rate": _model_contract_rate(cells),
        "FullPassByTrack": by_track,
    }
    _write_experiment_report(out, cells, report)
    return cells, report


def run_t5_matrix(
    out: Path,
    client: ModelClient,
    budget: ModelCallBudget,
    *,
    temperature: float,
    allow_live_model: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    evidence = _eval_evidence()
    start_calls = budget.snapshot()["calls_used"]
    cells: list[dict[str, Any]] = []
    for task in load_t5_tasks():
        for condition in T5_CONDITIONS:
            for track in T5_TRACKS:
                run_id = f"model_{task['id']}_{condition}_{track}_s0"
                run_dir = out / "runs" / run_id
                runner = RecordedModelRunner(
                    run_dir / "model_trace.jsonl",
                    client,
                    budget,
                    temperature=temperature,
                    allow_live_model=allow_live_model,
                    run_id=run_id,
                )
                loop = run_t5_cell(task, condition, track, run_dir, runner)
                cell = score_t5_cell(
                    task=task,
                    condition=condition,
                    track=track,
                    seed=0,
                    loop=loop,
                    eval_mode_evidence=evidence,
                )
                _write_cell(run_dir, cell)
                cells.append(cell)
    by_track = {
        track: {
            condition: _rate(
                [
                    cell
                    for cell in cells
                    if _context(cell).get("track") == track
                    and _context(cell).get("variant") == condition
                ]
            )
            for condition in T5_CONDITIONS
        }
        for track in T5_TRACKS
    }
    workflow = summarize_workflow("model_pilot_t5_v1", cells)
    calls = budget.snapshot()["calls_used"] - start_calls
    calibration_pass = (
        len(cells) == 18
        and by_track["full"]
        == {"no_policy": 1.0, "real_policy": 1.0, "placebo_policy": 1.0}
        and by_track["disconnect_policy"]
        == {"no_policy": 1.0, "real_policy": None, "placebo_policy": None}
        and _model_contract_rate(cells) == 1.0
    )
    report = {
        "experiment_id": "MODEL-PILOT-T5-v1",
        "base_release": "benchmark-v1.1-rule",
        "phase": "model_seed0_pilot",
        "offline_fixture_calibration_pass": calibration_pass
        if not client.info.live
        else None,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "model_calls": calls,
        "model_contract_rate": _model_contract_rate(cells),
        "FullPassByCondition": by_track,
    }
    _write_experiment_report(out, cells, report)
    return cells, report


def run_pilot(
    out: Path,
    client: ModelClient,
    *,
    experiment: str,
    temperature: float,
    max_calls: int,
    allow_live_model: bool,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    budget = ModelCallBudget(max_calls)
    reports: dict[str, Any] = {}
    if experiment in {"t4", "both"}:
        _, reports["t4"] = run_t4_matrix(
            out / "t4",
            client,
            budget,
            temperature=temperature,
            allow_live_model=allow_live_model,
        )
    if experiment in {"t5", "both"}:
        _, reports["t5"] = run_t5_matrix(
            out / "t5",
            client,
            budget,
            temperature=temperature,
            allow_live_model=allow_live_model,
        )
    offline_ok = not client.info.live and all(
        report.get("offline_fixture_calibration_pass") is True
        for report in reports.values()
    )
    summary = {
        "pilot_id": "MODEL-PILOT-T4-T5-v1",
        "base_release": "benchmark-v1.1-rule",
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "live_model_explicitly_allowed": allow_live_model,
        "temperature": temperature,
        "experiment": experiment,
        "gate": (
            "offline_runner_calibration_pass"
            if offline_ok
            else "model_pilot_recorded"
            if client.info.live
            else "offline_runner_calibration_failed"
        ),
        "ranking_eligible": False,
        "budget": budget.snapshot(),
        "reports": reports,
    }
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(summary, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=("t4", "t5", "both"), default="both")
    parser.add_argument("--provider", help="Configured GAWorld provider name")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--fixture-oracle", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--max-calls", type=int, default=160)
    parser.add_argument(
        "--out", type=Path, default=BRIDGE_ROOT / "output" / "model_pilot_t4_t5_v1"
    )
    args = parser.parse_args()
    if args.fixture_oracle:
        if args.provider or args.allow_live_model:
            parser.error(
                "--fixture-oracle cannot be combined with live provider options"
            )
        client: ModelClient = oracle_fixture_client()
    else:
        if not args.allow_live_model:
            parser.error("live model execution requires --allow-live-model")
        if not args.provider:
            parser.error("live model execution requires --provider")
        ensure_import_paths()
        client = GAWorldModelClient(
            args.provider,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    summary = run_pilot(
        args.out,
        client,
        experiment=args.experiment,
        temperature=args.temperature,
        max_calls=args.max_calls,
        allow_live_model=args.allow_live_model,
    )
    print(yaml.safe_dump(summary, allow_unicode=True, sort_keys=False))
    return 0 if summary["gate"] != "offline_runner_calibration_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
