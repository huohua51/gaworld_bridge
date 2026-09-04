"""Run the frozen T4-v2 protocol as a preregistered gpt-5.4 replication."""

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
from benchmark_core.model_runner_v2 import (
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from exp_gm_t4_02.loader import TRACKS, VARIANTS, load_tasks, payload_for
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.t4_v2 import _prompt, _validate, run_cell
from model_pilot.t4_v2_scorer import SCORER_VERSION, WORKFLOW_ID, score_cell
from v0_first_batch.paths import BRIDGE_ROOT, GAWORLD_ROOT, ensure_import_paths
from v0_first_batch.schema import summarize_workflow

REGISTRATION_PATH = (
    Path(__file__).with_name("registrations")
    / "T4_REGISTERED_TRANSPORT_GPT54_v1.yaml"
)
TASK_IDS = (
    "t4v2_reservoir_quality_001",
    "t4v2_substation_load_001",
    "t4v2_school_air_001",
)
PROVIDER = "paratera_glm"
MODEL = "gpt-5.4"
BASE_URL = "https://llmapi.paratera.com/v1"
MAX_CALLS = 60
CALIBRATION_CALLS = 2
MAX_TOKENS = 256
TEMPERATURE = 0.0
THINKING = "disabled"
RESPONSE_FORMAT = {"type": "json_object"}
RETRY_ATTEMPTS = 1
JSON_NORMALIZATION = "strict"


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
    provider = payload.get("provider") or {}
    if tuple(design.get("task_ids") or ()) != TASK_IDS:
        errors.append("registered_task_order_mismatch")
    if tuple(design.get("variants") or ()) != VARIANTS:
        errors.append("registered_variant_order_mismatch")
    if tuple(design.get("tracks") or ()) != TRACKS:
        errors.append("registered_track_order_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("registered_call_budget_mismatch")
    if int(design.get("calibration_calls") or 0) != CALIBRATION_CALLS:
        errors.append("registered_calibration_budget_mismatch")
    if str(design.get("prompt_protocol") or "") != "gaworld-benchmark-t4-model-v2":
        errors.append("registered_prompt_protocol_mismatch")
    if str(design.get("scorer_version") or "") != SCORER_VERSION:
        errors.append("registered_scorer_version_mismatch")
    expected_settings = {
        "name": PROVIDER,
        "model": MODEL,
        "base_url": BASE_URL,
        "temperature": TEMPERATURE,
        "thinking": THINKING,
        "max_tokens_per_call": MAX_TOKENS,
        "response_format": RESPONSE_FORMAT,
        "retry_attempts": RETRY_ATTEMPTS,
        "json_normalization": JSON_NORMALIZATION,
    }
    for key, expected in expected_settings.items():
        if provider.get(key) != expected:
            errors.append(f"provider_setting_mismatch:{key}")
    core_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(GAWORLD_ROOT), text=True
    ).strip()
    if core_commit != payload.get("required_gaworld_commit"):
        errors.append(f"gaworld_commit_mismatch:{core_commit}")
    if errors:
        raise RuntimeError("preregistration validation failed: " + ",".join(errors))
    return payload, _sha256(REGISTRATION_PATH)


def _eval_evidence() -> dict[str, Any]:
    ensure_import_paths()
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _context(cell: dict[str, Any]) -> dict[str, Any]:
    return (cell.get("extra") or {}).get("run_context") or {}


def _rate(cells: list[dict[str, Any]]) -> float | None:
    scored = [cell for cell in cells if cell.get("full_pass") is not None]
    if not scored:
        return None
    return round(sum(int(cell["full_pass"]) for cell in scored) / len(scored), 4)


def _contract_rate(cells: list[dict[str, Any]]) -> float:
    gates = [
        gate
        for cell in cells
        for gate in cell.get("gates") or []
        if gate.get("gate_id") == "model_responses_structured"
    ]
    return round(sum(bool(gate["passed"]) for gate in gates) / len(gates), 4) if gates else 0.0


def _live_client() -> GAWorldModelClient:
    os.environ["GAWORLD_LLM_API_BASE"] = BASE_URL
    os.environ["GAWORLD_LLM_MODEL"] = MODEL
    os.environ["GAWORLD_LLM_THINKING"] = THINKING
    os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
    ensure_import_paths()
    return GAWorldModelClient(
        PROVIDER,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        response_format=RESPONSE_FORMAT,
        retry_attempts=RETRY_ATTEMPTS,
    )


def run_calibration(out: Path, client: ModelClient) -> dict[str, Any]:
    registration, registration_hash = _registration()
    if not client.info.live or client.info.provider != PROVIDER or client.info.model_version != MODEL:
        raise ValueError("calibration requires the registered live provider/model")
    out.mkdir(parents=True, exist_ok=True)
    task = load_tasks()[0]
    payload = payload_for(task, "control")
    message = {
        "message_id": str(task["message_id"]),
        "message_class": str(task["message_class"]),
        "state_version": str(task["state_version"]),
        "payload": payload,
    }
    allowed = {"keep_current", str(task["intervention_payload"]["target_action"])}
    cases = [
        ("source", str(task["source"]), message, str(task["path"][1])),
        ("target", str(task["target"]), None, None),
    ]
    budget = ModelCallBudget(CALIBRATION_CALLS)
    responses = []
    for index, (role, node_id, received, next_node) in enumerate(cases, start=1):
        runner = RecordedModelRunner(
            out / f"calibration_{index}" / "model_trace.jsonl",
            client,
            budget,
            temperature=TEMPERATURE,
            allow_live_model=True,
            run_id=f"t4v2_gpt54_calibration_{index}",
            json_normalization=JSON_NORMALIZATION,
        )
        response = runner.call_json(
            _prompt(
                role=role,
                node_id=node_id,
                message=received,
                next_node=next_node,
                allowed_actions=sorted(allowed),
            ),
            task="benchmark_t4_v2",
            agent_id=node_id,
            validator=_validate(role, allowed),
        )
        responses.append(
            {
                "case": index,
                "role": role,
                "ok": response.ok,
                "normalization_applied": response.normalization_applied,
                "evidence_id": response.evidence_id,
            }
        )
    snapshot = budget.snapshot()
    passed = bool(
        len(responses) == CALIBRATION_CALLS
        and all(item["ok"] and not item["normalization_applied"] for item in responses)
        and snapshot["transport_attempts_observed"] == CALIBRATION_CALLS
        and snapshot["transport_retries_observed"] == 0
    )
    report = {
        "experiment_id": "MODEL-PILOT-T4-v2-GPT54",
        "phase": "non_scoring_live_calibration",
        "gate": "calibration_pass" if passed else "calibration_failed",
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_hash,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "ranking_eligible": False,
        "responses": responses,
        "budget": snapshot,
    }
    (out / "CALIBRATION_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return report


def _validate_calibration(path: Path, registration_hash: str) -> tuple[dict[str, Any], str]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    errors = []
    if manifest.get("gate") != "calibration_pass":
        errors.append("calibration_gate_not_passed")
    if manifest.get("registration_sha256") != registration_hash:
        errors.append("calibration_registration_mismatch")
    if manifest.get("model_version") != MODEL or manifest.get("provider") != PROVIDER:
        errors.append("calibration_model_mismatch")
    budget = manifest.get("budget") or {}
    if int(budget.get("calls_used") or 0) != CALIBRATION_CALLS:
        errors.append("calibration_call_count_mismatch")
    if int(budget.get("transport_attempts_observed") or 0) != CALIBRATION_CALLS:
        errors.append("calibration_transport_attempt_count_mismatch")
    if int(budget.get("transport_retries_observed") or 0) != 0:
        errors.append("calibration_transport_retry_observed")
    if errors:
        raise RuntimeError("calibration validation failed: " + ",".join(errors))
    return manifest, _sha256(path)


def run_matrix(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
    calibration_manifest: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_hash = _registration()
    if client.info.live and (
        client.info.provider != PROVIDER or client.info.model_version != MODEL
    ):
        raise ValueError("live provider/model does not match preregistration")
    calibration_sha = None
    if client.info.live:
        if calibration_manifest is None:
            raise ValueError("live registered run requires calibration manifest")
        _, calibration_sha = _validate_calibration(calibration_manifest, registration_hash)
    out.mkdir(parents=True, exist_ok=True)
    budget = ModelCallBudget(MAX_CALLS)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []
    for task in load_tasks():
        for variant in VARIANTS:
            for track in TRACKS:
                run_id = f"model_v2_gpt54_{task['id']}_{variant}_{track}_s0"
                run_dir = out / "runs" / run_id
                print(f"run {run_id}", flush=True)
                runner = RecordedModelRunner(
                    run_dir / "model_trace.jsonl",
                    client,
                    budget,
                    temperature=TEMPERATURE,
                    allow_live_model=allow_live_model,
                    run_id=run_id,
                    json_normalization=JSON_NORMALIZATION,
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
                cell.setdefault("extra", {})["replication_experiment_id"] = "MODEL-PILOT-T4-v2-GPT54"
                (run_dir / "cell_result.json").write_text(
                    json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
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
    snapshot = budget.snapshot()
    expected_tracks = {
        "full": {"control": 1.0, "intervention": 1.0},
        "remove_bridge": {"control": 1.0, "intervention": 0.0},
        "drop_bridge": {"control": 1.0, "intervention": 0.0},
    }
    passed = bool(
        len(cells) == 18
        and workflow["coverage"] == 1.0
        and contract_rate == 1.0
        and by_track == expected_tracks
        and snapshot["calls_used"] == MAX_CALLS
        and (not client.info.live or (
            snapshot["transport_attempts_observed"] == MAX_CALLS
            and snapshot["transport_retries_observed"] == 0
        ))
    )
    report = {
        "experiment_id": "MODEL-PILOT-T4-v2-GPT54",
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_hash,
        "phase": "second_model_seed0_replication" if client.info.live else "offline_fixture_calibration",
        "gate": "pass" if passed else "replication_failed",
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "ranking_eligible": False,
        "prompt_protocol": "gaworld-benchmark-t4-model-v2",
        "scorer_version": SCORER_VERSION,
        "n_cells": len(cells),
        "coverage": workflow["coverage"],
        "model_contract_rate": contract_rate,
        "FullPassByTrack": by_track,
        "budget": snapshot,
        "calibration_manifest": str(calibration_manifest) if calibration_manifest else None,
        "calibration_manifest_sha256": calibration_sha,
        "reference_glm52_manifest": registration["reference_glm52"]["manifest"],
        "reference_glm52_manifest_sha256": registration["reference_glm52"]["sha256"],
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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture-oracle", action="store_true")
    mode.add_argument("--live-calibration", action="store_true")
    mode.add_argument("--live-run", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--calibration-manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.fixture_oracle:
        if args.provider or args.allow_live_model or args.calibration_manifest:
            parser.error("fixture mode cannot use live options")
        _, report = run_matrix(
            args.out, oracle_fixture_client(), allow_live_model=False
        )
    else:
        if args.provider != PROVIDER or not args.allow_live_model:
            parser.error("live mode requires --provider paratera_glm --allow-live-model")
        client = _live_client()
        if args.live_calibration:
            if args.calibration_manifest:
                parser.error("calibration does not accept a calibration manifest")
            report = run_calibration(args.out, client)
        else:
            if args.calibration_manifest is None:
                parser.error("live run requires --calibration-manifest")
            _, report = run_matrix(
                args.out,
                client,
                allow_live_model=True,
                calibration_manifest=args.calibration_manifest,
            )
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] in {"pass", "calibration_pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
