"""Offline wiring tests for the preregistered T5-v2 model pilot."""

from __future__ import annotations

import json
from pathlib import Path

from model_pilot.t5_v2_fixture import oracle_fixture_client
from model_pilot.t5_v2_run import _registration, run_registered


def test_t5_v2_registration_hashes_and_design_are_valid() -> None:
    registration, registration_sha256 = _registration()

    assert registration["preregistration_id"] == "T5-EXPLICIT-SEMANTICS-GLM52-v2"
    assert len(registration_sha256) == 64


def test_t5_v2_fixture_calibrates_registered_semantics_and_contrasts(
    tmp_path: Path,
) -> None:
    out = tmp_path / "t5-v2-model"
    summary = run_registered(
        out,
        oracle_fixture_client(),
        allow_live_model=False,
    )

    assert summary["gate"] == "offline_t5_v2_calibration_pass"
    assert summary["registered_design_adherent"] is True
    assert summary["all_registered_outcomes_pass"] is True
    assert summary["n_cells"] == 9
    assert summary["budget"]["calls_used"] == 36
    assert summary["FullPassByPolicyState"] == {
        "absence": 1.0,
        "binding": 1.0,
        "nonbinding": 1.0,
    }
    assert summary["BehaviorChangeRateByPolicyState"] == {
        "absence": 0.0,
        "binding": 0.5,
        "nonbinding": 0.0,
    }
    assert summary["causal_contrasts"] == {
        "binding_minus_absence": 0.5,
        "binding_minus_nonbinding": 0.5,
        "nonbinding_minus_absence": 0.0,
    }
    assert summary["model_contract_rate"] == 1.0
    assert summary["policy_semantics_rate"] == 1.0
    assert summary["policy_response_rate"] == 1.0

    first_trace = Path(summary["cells"][0]["model_trace_path"])
    request = next(
        json.loads(line)
        for line in first_trace.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("event") == "model_request"
    )
    prompt = json.loads(request["prompt"])
    assert prompt["protocol"] == "gaworld-benchmark-t5-model-v2"
    assert prompt["registered_policy_state"]["status"] == "absence"
    assert any(
        rule.startswith("nonbinding: notice_seen=true, binding=false")
        for rule in prompt["registered_policy_rules"]
    )
