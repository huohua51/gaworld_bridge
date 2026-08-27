"""Offline wiring tests for preregistered T5-v3 repeats 1/2."""

from __future__ import annotations

import json
from pathlib import Path

from model_pilot.t5_v3_fixture import oracle_fixture_client
from model_pilot.t5_v3_repeats import _registration, run_registered


def test_t5_v3_repeat_registration_hashes_and_design_are_valid() -> None:
    registration, registration_sha256 = _registration()

    assert registration["preregistration_id"] == (
        "T5-ELIGIBILITY-SCOPE-GLM52-REPEATS-v1"
    )
    assert len(registration_sha256) == 64


def test_t5_v3_fixture_calibrates_scope_and_repeat_agreement(tmp_path: Path) -> None:
    out = tmp_path / "t5-v3-repeats"
    summary = run_registered(
        out,
        oracle_fixture_client(),
        allow_live_model=False,
    )

    assert summary["gate"] == "offline_t5_v3_repeat_calibration_pass"
    assert summary["registered_design_adherent"] is True
    assert summary["all_registered_outcomes_pass"] is True
    assert summary["new_cells"] == 18
    assert summary["budget"]["calls_used"] == 72
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
    assert summary["scope_prompt_rate"] == 1.0
    assert summary["model_contract_rate"] == 1.0
    assert summary["scope_semantics_rate"] == 1.0
    assert summary["resident_directive_rate"] == 1.0
    assert summary["policy_response_rate"] == 1.0
    assert summary["repeat_exact_agreement_rate"] == 1.0
    assert all(
        item["prompt_stable_across_repeats"]
        for item in summary["by_task_policy_state"].values()
    )

    nonbinding = next(
        item
        for item in summary["cells"]
        if item["policy_state"] == "nonbinding" and item["repeat_id"] == 1
    )
    trace = Path(nonbinding["model_trace_path"])
    requests = [
        json.loads(line)
        for line in trace.read_text(encoding="utf-8").splitlines()
        if json.loads(line).get("event") == "model_request"
    ]
    prompts = [json.loads(request["prompt"]) for request in requests]
    target_prompt = next(
        prompt for prompt in prompts if prompt["resident_directive"]["target_match"]
    )
    assert target_prompt["resident_directive"] == {
        "action": "keep_current",
        "authority": "sole_action_authority",
        "authorized": False,
        "target_match": True,
    }
    assert "required_action" not in target_prompt["policy_context"]["notice"]
