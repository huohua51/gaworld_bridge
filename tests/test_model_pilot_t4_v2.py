"""Offline calibration tests for the T4-v2 model protocol."""

from __future__ import annotations

import json

from benchmark_core.model_runner import (
    CallableModelClient,
    ModelCallBudget,
    RecordedModelRunner,
)
from exp_gm_t4_02.loader import load_tasks
from model_pilot.fixtures import oracle_fixture_client
from model_pilot.t4_v2 import run_cell
from model_pilot.t4_v2_run import _eval_evidence, run_matrix
from model_pilot.t4_v2_scorer import score_cell


def test_t4_v2_offline_fixture_calibrates_all_cells(tmp_path) -> None:
    cells, report = run_matrix(
        tmp_path / "pilot-v2",
        oracle_fixture_client(),
        temperature=0,
        max_calls=60,
        allow_live_model=False,
    )

    assert len(cells) == 18
    assert report["gate"] == "offline_runner_calibration_pass"
    assert report["live_model"] is False
    assert report["ranking_eligible"] is False
    assert report["model_contract_rate"] == 1.0
    assert report["budget"]["max_calls"] == 60
    assert report["budget"]["calls_used"] == 60
    assert report["budget"]["calls_remaining"] == 0
    assert report["FullPassByTrack"]["full"] == {
        "control": 1.0,
        "intervention": 1.0,
    }
    assert report["FullPassByTrack"]["remove_bridge"] == {
        "control": 1.0,
        "intervention": 0.0,
    }
    assert report["FullPassByTrack"]["drop_bridge"] == {
        "control": 1.0,
        "intervention": 0.0,
    }


def test_t4_v2_prompt_registers_transport_independent_of_action(tmp_path) -> None:
    run_matrix(
        tmp_path / "pilot-v2",
        oracle_fixture_client(),
        temperature=0,
        max_calls=60,
        allow_live_model=False,
    )
    prompts = []
    for path in (tmp_path / "pilot-v2").rglob("model_trace.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("event") == "model_request":
                prompts.append(json.loads(row["prompt"]))

    assert prompts
    assert all(item["protocol"] == "gaworld-benchmark-t4-model-v2" for item in prompts)
    assert all(item["message_class"] == "registered_status_update" for item in prompts)
    assert all(
        "action_required affects only target action, never transport"
        in item["registered_transport_rules"]
        for item in prompts
    )


def test_t4_v2_full_control_fails_if_source_uses_relevance_filter(tmp_path) -> None:
    def relevance_filter(prompt: str, task: str, agent_id: str | None) -> str:
        payload = json.loads(prompt)
        if payload["role"] == "source":
            return '{"forward":false,"reason":"no action requested"}'
        return (
            '{"accept":false,"target_action":"keep_current",'
            '"reason":"message not received"}'
        )

    task = load_tasks()[0]
    run_dir = tmp_path / "relevance-filter"
    runner = RecordedModelRunner(
        run_dir / "model_trace.jsonl",
        CallableModelClient(relevance_filter),
        ModelCallBudget(4),
        temperature=0,
        allow_live_model=False,
        run_id="t4-v2-relevance-filter",
    )
    loop = run_cell(task, "control", "full", run_dir, runner)
    cell = score_cell(
        task=task,
        variant="control",
        track="full",
        seed=0,
        loop=loop,
        eval_mode_evidence=_eval_evidence(),
    )

    criteria = {item["criterion_id"]: item for item in cell["criteria"]}
    assert cell["measurement_valid"] is True
    assert cell["full_pass"] == 0
    assert criteria["target_action_correct"]["passed"] is True
    assert criteria["target_update_accepted"]["passed"] is False
    assert criteria["complete_propagation_path"]["passed"] is False
    assert cell["process_profile"]["first_error"] == "registered_update_not_delivered"
