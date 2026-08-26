"""Offline calibration tests for the preregistered T4 consistency pilot."""

from __future__ import annotations

import yaml

from model_pilot.control_consistency import run_registered
from model_pilot.fixtures import oracle_fixture_client


def test_registered_consistency_runner_executes_exact_frozen_design(tmp_path) -> None:
    summary = run_registered(
        tmp_path / "consistency",
        oracle_fixture_client(),
        allow_live_model=False,
    )

    assert summary["registered_design_adherent"] is True
    assert summary["n_cells"] == 9
    assert summary["budget"]["max_calls"] == 36
    assert summary["budget"]["calls_used"] == 36
    assert summary["pooled"]["source_forward_rate"] == 1.0
    assert summary["pooled"]["complete_path_rate"] == 1.0
    assert summary["pooled"]["full_pass_rate"] == 1.0
    assert summary["pooled"]["model_contract_rate"] == 1.0
    assert all(
        item["source_forward_exact_agreement"] is True
        and item["prompt_stable_across_replicates"] is True
        for item in summary["by_task"].values()
    )

    manifest = yaml.safe_load(
        (tmp_path / "consistency" / "CONSISTENCY_MANIFEST.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["registration_sha256"] == summary["registration_sha256"]
    assert len(manifest["cells"]) == 9
