"""Run the independent T4-v2 model matrix with an explicit call budget."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
from exp_gm_t4_02.loader import TRACKS, VARIANTS, load_tasks
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.t4_v2 import run_cell
from model_pilot.t4_v2_scorer import SCORER_VERSION, WORKFLOW_ID, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

REGISTRATION_PATH = (
    Path(__file__).with_name("registrations")
    / "T4_REGISTERED_TRANSPORT_GLM52_v2.yaml"
)
TASK_IDS = (
    "t4v2_reservoir_quality_001",
    "t4v2_substation_load_001",
    "t4v2_school_air_001",
)
MAX_CALLS = 60
MAX_TOKENS = 256
TEMPERATURE = 0.0
THINKING = "disabled"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registration() -> tuple[dict[str, Any], str]:
    payload = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    for relative, expected in (payload.get("frozen_inputs") or {}).items():
        path = BRIDGE_ROOT / str(relative)
        if not path.is_file():
            errors.append(f"missing:{relative}")
            continue
        actual = _sha256(path)
        if actual != str(expected):
            errors.append(f"sha256_mismatch:{relative}:{actual}")
    design = payload.get("design") or {}
    if tuple(design.get("task_ids") or ()) != TASK_IDS:
        errors.append("registered_task_order_mismatch")
    if tuple(design.get("variants") or ()) != VARIANTS:
        errors.append("registered_variant_order_mismatch")
    if tuple(design.get("tracks") or ()) != TRACKS:
        errors.append("registered_track_order_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("registered_call_budget_mismatch")
    if str(design.get("scorer_version") or "") != SCORER_VERSION:
        errors.append("registered_scorer_version_mismatch")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


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


def _context(cell: dict[str, Any]) -> dict[str, Any]:
    return (cell.get("extra") or {}).get("run_context") or {}


def _rate(cells: list[dict[str, Any]]) -> float | None:
    scored = [cell for cell in cells if cell.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(cell["full_pass"]) for cell in scored) / len(scored), 4)


def _model_contract_rate(cells: list[dict[str, Any]]) -> float:
    gates = [
        gate
        for cell in cells
        for gate in cell.get("gates") or []
        if gate.get("gate_id") == "model_responses_structured"
    ]
    if not gates:
        return 0.0
    return round(sum(bool(gate["passed"]) for gate in gates) / len(gates), 4)


def run_matrix(
    out: Path,
    client: ModelClient,
    *,
    temperature: float,
    max_calls: int,
    allow_live_model: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_sha256 = _registration()
    if max_calls != MAX_CALLS:
        raise ValueError(f"T4-v2 registered matrix requires max_calls={MAX_CALLS}")
    if temperature != TEMPERATURE:
        raise ValueError(f"T4-v2 registered matrix requires temperature={TEMPERATURE}")
    if client.info.live:
        provider = registration.get("provider") or {}
        if client.info.provider != str(provider.get("name")):
            raise ValueError("live provider does not match preregistration")
        if client.info.model_version != str(provider.get("model")):
            raise ValueError("live model does not match preregistration")
    out.mkdir(parents=True, exist_ok=True)
    evidence = _eval_evidence()
    budget = ModelCallBudget(max_calls)
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                run_id = f"model_v2_{task['id']}_{variant}_{track}_s0"
                run_dir = out / "runs" / run_id
                runner = RecordedModelRunner(
                    run_dir / "model_trace.jsonl",
                    client,
                    budget,
                    temperature=temperature,
                    allow_live_model=allow_live_model,
                    run_id=run_id,
                )
                loop = run_cell(task, variant, track, run_dir, runner)
                cell = score_cell(
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
            for variant in VARIANTS
        }
        for track in TRACKS
    }
    workflow = summarize_workflow(WORKFLOW_ID, cells)
    contract_rate = _model_contract_rate(cells)
    calibrated = (
        not client.info.live
        and len(cells) == 18
        and workflow["coverage"] == 1.0
        and by_track["full"] == {"control": 1.0, "intervention": 1.0}
        and by_track["remove_bridge"]
        == {"control": 1.0, "intervention": 0.0}
        and by_track["drop_bridge"]
        == {"control": 1.0, "intervention": 0.0}
        and contract_rate == 1.0
    )
    report = {
        "experiment_id": "MODEL-PILOT-T4-v2",
        "preregistration_id": registration["preregistration_id"],
        "registration_path": str(REGISTRATION_PATH),
        "registration_sha256": registration_sha256,
        "registered_base_commit": registration["base_commit"],
        "base_release": "benchmark-v1.1-rule",
        "phase": "model_seed0_pilot" if client.info.live else "offline_fixture_calibration",
        "gate": (
            "offline_runner_calibration_pass"
            if calibrated
            else "model_pilot_recorded"
            if client.info.live
            else "offline_runner_calibration_failed"
        ),
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "live_model_explicitly_allowed": allow_live_model,
        "prompt_protocol": "gaworld-benchmark-t4-model-v2",
        "ranking_eligible": False,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "model_contract_rate": contract_rate,
        "FullPassByTrack": by_track,
        "budget": budget.snapshot(),
    }
    (out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", help="Configured GAWorld provider name")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--fixture-oracle", action="store_true")
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS)
    parser.add_argument(
        "--out", type=Path, default=BRIDGE_ROOT / "output" / "model_pilot_t4_v2"
    )
    args = parser.parse_args()
    if args.temperature != TEMPERATURE:
        parser.error(f"registered run requires --temperature {TEMPERATURE}")
    if args.max_tokens != MAX_TOKENS:
        parser.error(f"registered run requires --max-tokens {MAX_TOKENS}")
    if args.max_calls != MAX_CALLS:
        parser.error(f"registered run requires --max-calls {MAX_CALLS}")
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
        registration, _ = _registration()
        provider = registration.get("provider") or {}
        if args.provider != str(provider.get("name")):
            parser.error("registered live run requires provider paratera_glm")
        os.environ["GAWORLD_LLM_MODEL"] = str(provider["model"])
        os.environ["GAWORLD_LLM_THINKING"] = THINKING
        os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
        ensure_import_paths()
        client = GAWorldModelClient(
            args.provider,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        if client.info.model_version != str(provider["model"]):
            parser.error("registered live run requires model GLM-5.2")
    _, report = run_matrix(
        args.out,
        client,
        temperature=args.temperature,
        max_calls=args.max_calls,
        allow_live_model=args.allow_live_model,
    )
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] != "offline_runner_calibration_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
