"""Run the registered GAWorld T4-v2 matrix through YuLan-OneSim EventBus."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
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
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

# The frozen T4 prompt module imports GAWorld's network channel at module load
# time even though the YuLan adapter does not use that channel.
ensure_import_paths()

from cross_platform.yulan_onesim.t4_adapter import run_cell
from cross_platform.yulan_onesim.t4_scorer import SCORER_VERSION, WORKFLOW_ID, score_cell
from exp_gm_t4_02.loader import TRACKS, VARIANTS, load_tasks
from model_pilot.fixtures import oracle_fixture_client
from v0_first_batch.schema import summarize_workflow

REGISTRATION_PATH = Path(__file__).with_name("registration_t4_glm52.yaml")
YULAN_ROOT = Path(r"F:\proj\YuLan-OneSim-official")
YULAN_COMMIT = "9829d722b528b733f8c8317315637071fa23b206"
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
        elif _sha256(path) != str(expected):
            errors.append(f"sha256_mismatch:{relative}:{_sha256(path)}")
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
    actual_commit = subprocess.run(
        ["git", "-C", str(YULAN_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_commit != YULAN_COMMIT:
        errors.append(f"yulan_commit_mismatch:{actual_commit}")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _eval_evidence() -> dict[str, Any]:
    ensure_import_paths()
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _rate(cells: list[dict[str, Any]]) -> float | None:
    scored = [cell for cell in cells if cell.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(cell["full_pass"]) for cell in scored) / len(scored), 4)


def _context(cell: dict[str, Any]) -> dict[str, Any]:
    return (cell.get("extra") or {}).get("run_context") or {}


def _contract_rate(cells: list[dict[str, Any]]) -> float:
    gates = [
        gate
        for cell in cells
        for gate in cell.get("gates") or []
        if gate.get("gate_id") == "model_responses_structured"
    ]
    return round(sum(bool(gate["passed"]) for gate in gates) / len(gates), 4)


def run_matrix(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_sha256 = _registration()
    if client.info.live:
        provider = registration["provider"]
        if client.info.provider != provider["name"] or client.info.model_version != provider["model"]:
            raise ValueError("live provider/model does not match preregistration")
    out.mkdir(parents=True, exist_ok=False)
    evidence = _eval_evidence()
    budget = ModelCallBudget(MAX_CALLS)
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                run_id = f"yulan_model_v2_{task['id']}_{variant}_{track}_s0"
                run_dir = out / "runs" / run_id
                runner = RecordedModelRunner(
                    run_dir / "model_trace.jsonl",
                    client,
                    budget,
                    temperature=TEMPERATURE,
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
                (run_dir / "cell_result.json").write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                cells.append(cell)

    by_track = {
        track: {
            variant: _rate([
                cell for cell in cells
                if _context(cell).get("track") == track
                and _context(cell).get("variant") == variant
            ])
            for variant in VARIANTS
        }
        for track in TRACKS
    }
    workflow = summarize_workflow(WORKFLOW_ID, cells)
    contract_rate = _contract_rate(cells)
    calibrated = (
        not client.info.live
        and len(cells) == 18
        and workflow["coverage"] == 1.0
        and by_track["full"] == {"control": 1.0, "intervention": 1.0}
        and by_track["remove_bridge"] == {"control": 1.0, "intervention": 0.0}
        and by_track["drop_bridge"] == {"control": 1.0, "intervention": 0.0}
        and contract_rate == 1.0
    )
    report = {
        "experiment_id": "CROSS-PLATFORM-YULAN-T4-v2",
        "preregistration_id": registration["preregistration_id"],
        "registration_path": str(REGISTRATION_PATH),
        "registration_sha256": registration_sha256,
        "yulan_repository": registration["systems"]["yulan_onesim"]["repository"],
        "yulan_commit": YULAN_COMMIT,
        "comparison_reference": registration["systems"]["gaworld_reference"],
        "phase": "live_protocol_parity" if client.info.live else "offline_fixture_calibration",
        "gate": "offline_runner_calibration_pass" if calibrated else "model_pilot_recorded" if client.info.live else "offline_runner_calibration_failed",
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "live_model_explicitly_allowed": allow_live_model,
        "prompt_protocol": "gaworld-benchmark-t4-model-v2",
        "scorer_version": SCORER_VERSION,
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
    parser.add_argument("--provider")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--fixture-oracle", action="store_true")
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if (args.temperature, args.max_tokens, args.max_calls) != (TEMPERATURE, MAX_TOKENS, MAX_CALLS):
        parser.error("registered run requires temperature=0, max-tokens=256, max-calls=60")
    if args.fixture_oracle:
        if args.provider or args.allow_live_model:
            parser.error("fixture cannot be combined with live options")
        client: ModelClient = oracle_fixture_client()
    else:
        if not args.allow_live_model or args.provider != "paratera_glm":
            parser.error("live run requires --provider paratera_glm --allow-live-model")
        os.environ["GAWORLD_LLM_MODEL"] = "GLM-5.2"
        os.environ["GAWORLD_LLM_THINKING"] = THINKING
        os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
        ensure_import_paths()
        client = GAWorldModelClient(
            args.provider,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
    _, report = run_matrix(args.out, client, allow_live_model=args.allow_live_model)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] != "offline_runner_calibration_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
