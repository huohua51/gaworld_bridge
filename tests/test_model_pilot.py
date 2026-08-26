"""Offline calibration and evidence tests for the T4/T5 model pilot."""

from __future__ import annotations

import json

from benchmark_core.model_runner import (
    CallableModelClient,
    ModelCallBudget,
    RecordedModelRunner,
)
from exp_gm_t4_01.loader import load_tasks as load_t4_tasks
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.run import _eval_evidence, run_pilot
from model_pilot.smoke import run_smoke
from model_pilot.t4 import run_cell as run_t4_cell
from model_pilot.t4_scorer import score_cell as score_t4_cell


def test_offline_fixture_calibrates_both_model_matrices(tmp_path) -> None:
    summary = run_pilot(
        tmp_path / "pilot",
        oracle_fixture_client(),
        experiment="both",
        temperature=0,
        max_calls=160,
        allow_live_model=False,
    )

    assert summary["gate"] == "offline_runner_calibration_pass"
    assert summary["live_model"] is False
    assert summary["ranking_eligible"] is False
    assert summary["reports"]["t4"]["n_cells"] == 18
    assert summary["reports"]["t5"]["n_cells"] == 18
    assert summary["reports"]["t4"]["model_contract_rate"] == 1.0
    assert summary["reports"]["t5"]["model_contract_rate"] == 1.0
    assert summary["budget"]["calls_used"] <= summary["budget"]["max_calls"]


def test_t5_prompts_do_not_expose_hidden_condition_labels(tmp_path) -> None:
    run_pilot(
        tmp_path / "pilot",
        oracle_fixture_client(),
        experiment="t5",
        temperature=0,
        max_calls=80,
        allow_live_model=False,
    )
    prompts = []
    for path in (tmp_path / "pilot").rglob("model_trace.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("event") == "model_request":
                prompts.append(str(row["prompt"]))

    assert prompts
    assert all("real_policy" not in prompt for prompt in prompts)
    assert all("placebo_policy" not in prompt for prompt in prompts)


def test_malformed_model_response_is_artifact_failure_without_fallback(
    tmp_path,
) -> None:
    client = CallableModelClient(
        lambda prompt, task, agent_id: "not-json",
        provider="malformed-fixture",
        model_version="malformed-v1",
    )
    task = load_t4_tasks()[0]
    run_dir = tmp_path / "malformed"
    runner = RecordedModelRunner(
        run_dir / "model_trace.jsonl",
        client,
        ModelCallBudget(10),
        temperature=0,
        allow_live_model=False,
        run_id="malformed-t4",
    )
    loop = run_t4_cell(task, "intervention", "full", run_dir, runner)
    cell = score_t4_cell(
        task=task,
        variant="intervention",
        track="full",
        seed=0,
        loop=loop,
        eval_mode_evidence=_eval_evidence(),
    )

    assert cell["measurement_valid"] is True
    assert cell["full_pass"] == 0
    gate = next(
        gate
        for gate in cell["gates"]
        if gate["gate_id"] == "model_responses_structured"
    )
    assert gate["passed"] is False
    assert cell["process_profile"]["first_error"] == "model_response_contract_invalid"


def test_t4_full_track_cannot_pass_when_model_stops_propagation(tmp_path) -> None:
    def stop_at_source(prompt: str, task: str, agent_id: str | None) -> str:
        payload = json.loads(prompt)
        if payload["role"] == "source":
            return '{"forward":false,"reason":"no action requested"}'
        return (
            '{"accept":false,"target_action":"keep_current",'
            '"reason":"message not received"}'
        )

    task = load_t4_tasks()[0]
    run_dir = tmp_path / "stopped-control"
    runner = RecordedModelRunner(
        run_dir / "model_trace.jsonl",
        CallableModelClient(stop_at_source),
        ModelCallBudget(4),
        temperature=0,
        allow_live_model=False,
        run_id="stopped-control",
    )
    loop = run_t4_cell(task, "control", "full", run_dir, runner)
    cell = score_t4_cell(
        task=task,
        variant="control",
        track="full",
        seed=0,
        loop=loop,
        eval_mode_evidence=_eval_evidence(),
    )

    path_criterion = next(
        item
        for item in cell["criteria"]
        if item["criterion_id"] == "complete_propagation_path"
    )
    assert cell["measurement_valid"] is True
    assert cell["full_pass"] == 0
    assert path_criterion["critical"] is True
    assert path_criterion["passed"] is False


def test_offline_smoke_records_one_call_without_ranking_claim(tmp_path) -> None:
    client = CallableModelClient(
        lambda prompt, task, agent_id: '{"status":"ok"}',
        provider="smoke-fixture",
        model_version="smoke-fixture-v1",
    )

    result = run_smoke(
        tmp_path / "smoke",
        client,
        temperature=0,
        allow_live_model=False,
    )

    assert result["ok"] is True
    assert result["ranking_eligible"] is False
    assert result["budget"]["calls_used"] == 1
