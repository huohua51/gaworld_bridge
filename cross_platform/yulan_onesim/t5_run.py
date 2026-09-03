"""Run the frozen GAWorld T5-v3 repeat-1 matrix on YuLan-OneSim EventBus."""

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

ensure_import_paths()

from cross_platform.yulan_onesim.t5_adapter import run_cell
from cross_platform.yulan_onesim.t5_scorer import SCORER_VERSION, WORKFLOW_ID, score_cell
from exp_gm_t5_03.loader import TASK_IDS, load_tasks
from exp_gm_t5_03.semantics import POLICY_STATES
from model_pilot.t5_v3 import PROMPT_PROTOCOL
from model_pilot.t5_v3_fixture import oracle_fixture_client

REGISTRATION_PATH = Path(__file__).with_name("registration_t5_glm52.yaml")
YULAN_ROOT = Path(r"F:\proj\YuLan-OneSim-official")
YULAN_COMMIT = "9829d722b528b733f8c8317315637071fa23b206"
GAWORLD_REFERENCE = BRIDGE_ROOT / "output" / (
    "model_pilot_live_t5_v3_repeats_glm52_e052783444814bafa16c26c21ebad5c6"
)
REPEAT_ID = 1
TRACK = "full"
MAX_CALLS = 36
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
    if tuple(design.get("policy_states") or ()) != POLICY_STATES:
        errors.append("registered_policy_state_order_mismatch")
    if tuple(design.get("repeat_ids") or ()) != (REPEAT_ID,):
        errors.append("registered_repeat_order_mismatch")
    if str(design.get("track") or "") != TRACK:
        errors.append("registered_track_mismatch")
    if int(design.get("max_calls") or 0) != MAX_CALLS:
        errors.append("registered_call_budget_mismatch")
    if str(design.get("prompt_protocol") or "") != PROMPT_PROTOCOL:
        errors.append("registered_prompt_protocol_mismatch")
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
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def _gate(cell: dict[str, Any], gate_id: str) -> bool:
    return bool(next(item for item in cell["gates"] if item["gate_id"] == gate_id)["passed"])


def _criterion(cell: dict[str, Any], criterion_id: str) -> bool:
    return bool(
        next(item for item in cell["criteria"] if item["criterion_id"] == criterion_id)[
            "passed"
        ]
    )


def _reference_cell(task_id: str, policy_state: str) -> dict[str, Any]:
    path = GAWORLD_REFERENCE / "runs" / (
        f"model_v3_{task_id}_{policy_state}_{TRACK}_r{REPEAT_ID}"
    ) / "cell_result.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _comparison(cell: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    process = cell["process_profile"]
    reference_process = reference["process_profile"]
    prompt_hashes = cell["extra"]["prompt_sha256_by_resident"]
    reference_hashes = reference["extra"]["prompt_sha256_by_resident"]
    scope_outputs = {
        item["agent_id"]: item["actual"] for item in process["scope_decisions"]
    }
    reference_scope_outputs = {
        item["agent_id"]: item["actual"]
        for item in reference_process["scope_decisions"]
    }
    return {
        "prompt_hashes_exact": prompt_hashes == reference_hashes,
        "scope_outputs_exact": scope_outputs == reference_scope_outputs,
        "actual_actions_exact": process["actual_actions"]
        == reference_process["actual_actions"],
        "full_pass_exact": cell["full_pass"] == reference["full_pass"],
        "yulan_full_pass": cell["full_pass"],
        "gaworld_full_pass": reference["full_pass"],
    }


def run_matrix(
    out: Path,
    client: ModelClient,
    *,
    allow_live_model: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registration, registration_sha256 = _registration()
    if client.info.live:
        provider = registration["provider"]
        if (
            client.info.provider != provider["name"]
            or client.info.model_version != provider["model"]
        ):
            raise ValueError("live provider/model does not match preregistration")
    out.mkdir(parents=True, exist_ok=False)
    evidence = _eval_evidence()
    budget = ModelCallBudget(MAX_CALLS, max_response_chars=2_000)
    cells: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for task in load_tasks():
        for policy_state in POLICY_STATES:
            run_id = f"yulan_model_v3_{task['id']}_{policy_state}_{TRACK}_r{REPEAT_ID}"
            run_dir = out / "runs" / run_id
            runner = RecordedModelRunner(
                run_dir / "model_trace.jsonl",
                client,
                budget,
                temperature=TEMPERATURE,
                allow_live_model=allow_live_model,
                run_id=run_id,
            )
            loop = run_cell(task, policy_state, TRACK, run_dir, runner)
            cell = score_cell(
                task=task,
                policy_state=policy_state,
                track=TRACK,
                repeat_id=REPEAT_ID,
                loop=loop,
                eval_mode_evidence=evidence,
            )
            cell_path = run_dir / "cell_result.json"
            cell_path.write_text(
                json.dumps(cell, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            reference = _reference_cell(str(task["id"]), policy_state)
            comparison = {
                "task_id": str(task["id"]),
                "policy_state": policy_state,
                **_comparison(cell, reference),
                "cell_result_path": str(cell_path),
            }
            cells.append(cell)
            comparisons.append(comparison)

    full_pass_by_state = {
        state: round(
            sum(
                int(cell.get("full_pass") or 0)
                for cell in cells
                if cell["extra"]["policy_state"] == state
            )
            / len(TASK_IDS),
            4,
        )
        for state in POLICY_STATES
    }
    model_contract_rate = round(
        sum(_gate(cell, "model_responses_structured") for cell in cells) / len(cells),
        4,
    )
    scope_semantics_rate = round(
        sum(_criterion(cell, "resident_scope_semantics_correct") for cell in cells)
        / len(cells),
        4,
    )
    directive_rate = round(
        sum(_criterion(cell, "resident_directive_followed") for cell in cells)
        / len(cells),
        4,
    )
    comparison_exact = {
        key: sum(bool(item[key]) for item in comparisons)
        for key in (
            "prompt_hashes_exact",
            "scope_outputs_exact",
            "actual_actions_exact",
            "full_pass_exact",
        )
    }
    offline_calibrated = bool(
        not client.info.live
        and len(cells) == 9
        and int(budget.snapshot()["calls_used"]) == MAX_CALLS
        and all(cell["measurement_valid"] and cell["full_pass"] == 1 for cell in cells)
        and all(item["prompt_hashes_exact"] for item in comparisons)
        and full_pass_by_state == {state: 1.0 for state in POLICY_STATES}
    )
    report = {
        "experiment_id": "CROSS-PLATFORM-YULAN-T5-v3",
        "preregistration_id": registration["preregistration_id"],
        "registration_path": str(REGISTRATION_PATH),
        "registration_sha256": registration_sha256,
        "yulan_repository": registration["systems"]["yulan_onesim"]["repository"],
        "yulan_commit": YULAN_COMMIT,
        "comparison_reference": registration["systems"]["gaworld_reference"],
        "phase": "live_protocol_parity" if client.info.live else "offline_fixture_calibration",
        "gate": (
            "offline_runner_calibration_pass"
            if offline_calibrated
            else "model_pilot_recorded"
            if client.info.live
            else "offline_runner_calibration_failed"
        ),
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "live_model_explicitly_allowed": allow_live_model,
        "prompt_protocol": PROMPT_PROTOCOL,
        "scorer_version": SCORER_VERSION,
        "ranking_eligible": False,
        "n_cells": len(cells),
        "FullPassByPolicyState": full_pass_by_state,
        "model_contract_rate": model_contract_rate,
        "scope_semantics_rate": scope_semantics_rate,
        "resident_directive_rate": directive_rate,
        "exact_matches_with_gaworld": {**comparison_exact, "denominator": len(comparisons)},
        "comparisons": comparisons,
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
    if (args.temperature, args.max_tokens, args.max_calls) != (
        TEMPERATURE,
        MAX_TOKENS,
        MAX_CALLS,
    ):
        parser.error("registered run requires temperature=0, max-tokens=256, max-calls=36")
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
        client = GAWorldModelClient(
            args.provider,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
    _, report = run_matrix(out=args.out, client=client, allow_live_model=args.allow_live_model)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 1 if report["gate"] == "offline_runner_calibration_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
