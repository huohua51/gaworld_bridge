#!/usr/bin/env python3
"""Run C1-07 by binding fresh inputs to the frozen C1-06 runner contract."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

from benchmark_core.model_runner_v2 import GAWorldModelClient, ModelClient
from exp_gm_c1_05.fixture import fixture_client
from exp_gm_c1_06 import run_matrix as frozen_runner
from exp_gm_c1_07.loader import TASK_IDS, VARIANTS, load_tasks
from exp_gm_c1_07.scorer import SCORER_VERSION, WORKFLOW_ID, score_cell
from v0_first_batch.paths import ensure_import_paths

REGISTRATION_PATH = Path(__file__).with_name("registration.yaml")


def _bind_fresh_inputs() -> None:
    frozen_runner.REGISTRATION_PATH = REGISTRATION_PATH
    frozen_runner.TASK_IDS = TASK_IDS
    frozen_runner.VARIANTS = VARIANTS
    frozen_runner.load_tasks = load_tasks
    frozen_runner.SCORER_VERSION = SCORER_VERSION
    frozen_runner.WORKFLOW_ID = WORKFLOW_ID
    frozen_runner.score_cell = score_cell


def _live_client() -> GAWorldModelClient:
    os.environ["GAWORLD_LLM_API_BASE"] = frozen_runner.BASE_URL
    os.environ["GAWORLD_LLM_MODEL"] = frozen_runner.MODEL
    os.environ["GAWORLD_LLM_THINKING"] = frozen_runner.THINKING
    os.environ.pop("GAWORLD_LLM_REASONING_EFFORT", None)
    ensure_import_paths()
    return GAWorldModelClient(
        frozen_runner.PROVIDER,
        temperature=frozen_runner.TEMPERATURE,
        max_tokens=frozen_runner.MAX_TOKENS,
        response_format=frozen_runner.RESPONSE_FORMAT,
        retry_attempts=frozen_runner.RETRY_ATTEMPTS,
    )


def run(out: Path, client: ModelClient, *, allow_live_model: bool):
    _bind_fresh_inputs()
    cells, report = frozen_runner.run_matrix(
        out, client, allow_live_model=allow_live_model
    )
    report["experiment_id"] = "EXP-GM-C1-07"
    report["phase"] = (
        "postmerge_operational_replacement_seed0"
        if client.info.live
        else "offline_fixture_calibration"
    )
    report["does_not_overwrite"] = [
        "EXP-GM-C1-02",
        "EXP-GM-C1-03",
        "EXP-GM-C1-04",
        "EXP-GM-C1-05",
        "EXP-GM-C1-06",
    ]
    report["operational_replacement_for"] = "EXP-GM-C1-06"
    (out / "RUN_MANIFEST.yaml").write_text(
        yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return cells, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture-oracle", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.fixture_oracle:
        if args.provider or args.allow_live_model:
            parser.error("fixture mode cannot use live options")
        client: ModelClient = fixture_client()
        allow_live = False
    else:
        if args.provider != frozen_runner.PROVIDER or not args.allow_live_model:
            parser.error("live mode requires --provider paratera_glm --allow-live-model")
        client = _live_client()
        allow_live = True
    _, report = run(args.out, client, allow_live_model=allow_live)
    print(yaml.safe_dump(report, allow_unicode=True, sort_keys=False))
    return 0 if report["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
