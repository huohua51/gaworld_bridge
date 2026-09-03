"""Continue only the never-started cells after the externally aborted T4 run."""

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
from benchmark_core.model_runner import GAWorldModelClient, ModelCallBudget, RecordedModelRunner
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths

ensure_import_paths()

from cross_platform.yulan_onesim.t4_adapter import run_cell
from cross_platform.yulan_onesim.t4_scorer import SCORER_VERSION, score_cell
from exp_gm_t4_02.loader import load_tasks

REGISTRATION_PATH = Path(__file__).with_name("registration_t4_resume.yaml")
YULAN_ROOT = Path(r"F:\proj\YuLan-OneSim-official")
YULAN_COMMIT = "9829d722b528b733f8c8317315637071fa23b206"
TEMPERATURE = 0.0
MAX_TOKENS = 256
MAX_CALLS = 30
REMAINING_CELLS = (
    ("t4v2_substation_load_001", "intervention", "full"),
    ("t4v2_substation_load_001", "intervention", "remove_bridge"),
    ("t4v2_substation_load_001", "intervention", "drop_bridge"),
    ("t4v2_school_air_001", "control", "full"),
    ("t4v2_school_air_001", "control", "remove_bridge"),
    ("t4v2_school_air_001", "control", "drop_bridge"),
    ("t4v2_school_air_001", "intervention", "full"),
    ("t4v2_school_air_001", "intervention", "remove_bridge"),
    ("t4v2_school_air_001", "intervention", "drop_bridge"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_registration() -> tuple[dict[str, Any], str]:
    registration = yaml.safe_load(REGISTRATION_PATH.read_text(encoding="utf-8")) or {}
    errors: list[str] = []
    for relative, expected in (registration.get("frozen_inputs") or {}).items():
        path = BRIDGE_ROOT / str(relative)
        if not path.is_file():
            errors.append(f"missing:{relative}")
        elif _sha256(path) != str(expected):
            errors.append(f"sha256_mismatch:{relative}:{_sha256(path)}")
    registered_cells = tuple(
        (str(row["task_id"]), str(row["variant"]), str(row["track"]))
        for row in registration["design"]["remaining_cells"]
    )
    if registered_cells != REMAINING_CELLS:
        errors.append("remaining_cell_order_mismatch")
    if int(registration["design"]["max_calls"]) != MAX_CALLS:
        errors.append("call_budget_mismatch")
    actual_commit = subprocess.run(
        ["git", "-C", str(YULAN_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual_commit != YULAN_COMMIT:
        errors.append(f"yulan_commit_mismatch:{actual_commit}")
    if errors:
        raise RuntimeError("resume preregistration validation failed: " + ",".join(errors))
    return registration, _sha256(REGISTRATION_PATH)


def _eval_evidence() -> dict[str, Any]:
    from config import CONFIG

    config = deepcopy(CONFIG)
    config.setdefault("eval_mode", {})["enabled"] = True
    return capture_eval_mode_evidence(config)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--max-calls", type=int, default=MAX_CALLS)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_live_model or args.provider != "paratera_glm":
        parser.error("resume requires --provider paratera_glm --allow-live-model")
    if (args.temperature, args.max_tokens, args.max_calls) != (TEMPERATURE, MAX_TOKENS, MAX_CALLS):
        parser.error("registered resume requires temperature=0, max-tokens=256, max-calls=30")

    registration, registration_sha256 = _load_registration()
    args.out.mkdir(parents=True, exist_ok=False)
    os.environ["GAWORLD_LLM_MODEL"] = "GLM-5.2"
    os.environ["GAWORLD_LLM_THINKING"] = "disabled"
    os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
    client = GAWorldModelClient(
        "paratera_glm", temperature=TEMPERATURE, max_tokens=MAX_TOKENS
    )
    if client.info.model_version != "GLM-5.2":
        raise RuntimeError("configured model is not GLM-5.2")

    task_by_id = {str(task["id"]): task for task in load_tasks()}
    budget = ModelCallBudget(MAX_CALLS)
    evidence = _eval_evidence()
    cells: list[dict[str, Any]] = []
    for task_id, variant, track in REMAINING_CELLS:
        run_id = f"yulan_model_v2_{task_id}_{variant}_{track}_s0"
        run_dir = args.out / "runs" / run_id
        runner = RecordedModelRunner(
            run_dir / "model_trace.jsonl",
            client,
            budget,
            temperature=TEMPERATURE,
            allow_live_model=True,
            run_id=run_id,
        )
        loop = run_cell(task_by_id[task_id], variant, track, run_dir, runner)
        cell = score_cell(
            task=task_by_id[task_id],
            variant=variant,
            track=track,
            seed=0,
            loop=loop,
            eval_mode_evidence=evidence,
        )
        (run_dir / "cell_result.json").write_text(
            json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        cells.append(cell)

    report = {
        "experiment_id": "CROSS-PLATFORM-YULAN-T4-v2-CONTINUATION",
        "preregistration_id": registration["preregistration_id"],
        "registration_sha256": registration_sha256,
        "prior_partial_run": registration["prior_partial_run"],
        "yulan_commit": YULAN_COMMIT,
        "provider": "paratera_glm",
        "model_version": "GLM-5.2",
        "scorer_version": SCORER_VERSION,
        "live_model": True,
        "ranking_eligible": False,
        "completed_cells": len(cells),
        "budget": budget.snapshot(),
    }
    (args.out / "cell_table.json").write_text(
        json.dumps(cells, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

