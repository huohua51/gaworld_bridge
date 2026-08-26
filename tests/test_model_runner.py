"""Tests for the budgeted evidence-first model runner."""

from __future__ import annotations

import json

import pytest

from benchmark_core.model_runner import (
    CallableModelClient,
    LiveModelCallBlocked,
    ModelCallBudget,
    ModelCallBudgetExceeded,
    RecordedModelRunner,
)


def _validator(payload: dict[str, object]) -> list[str]:
    return [] if isinstance(payload.get("action"), str) else ["action_must_be_string"]


def test_runner_records_prompt_raw_response_and_parsed_json(tmp_path) -> None:
    client = CallableModelClient(
        lambda prompt, task, agent_id: json.dumps({"action": "keep_current"})
    )
    budget = ModelCallBudget(2)
    path = tmp_path / "model.jsonl"
    runner = RecordedModelRunner(
        path,
        client,
        budget,
        temperature=0,
        allow_live_model=False,
        run_id="cell-1",
    )

    response = runner.call_json(
        '{"instruction":"act"}',
        task="benchmark_t5",
        agent_id="resident-1",
        validator=_validator,
    )
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert response.ok is True
    assert response.parsed == {"action": "keep_current"}
    assert [row["event"] for row in rows] == ["model_request", "model_response"]
    assert rows[0]["prompt"] == '{"instruction":"act"}'
    assert rows[1]["raw_response"] == '{"action": "keep_current"}'
    assert runner.summary()["budget"]["calls_used"] == 1


def test_runner_rejects_non_strict_json_without_fallback(tmp_path) -> None:
    client = CallableModelClient(lambda prompt, task, agent_id: "```json\n{}\n```")
    runner = RecordedModelRunner(
        tmp_path / "model.jsonl",
        client,
        ModelCallBudget(1),
        temperature=0,
        allow_live_model=False,
        run_id="cell-2",
    )

    response = runner.call_json(
        "prompt", task="benchmark_t4", agent_id=None, validator=_validator
    )

    assert response.ok is False
    assert "json_parse_error" in response.error
    assert runner.summary()["invalid_responses"] == 1


def test_live_client_is_blocked_before_handler_and_budget(tmp_path) -> None:
    calls: list[str] = []
    client = CallableModelClient(
        lambda prompt, task, agent_id: calls.append(prompt) or "{}",
        provider="live-test",
        live=True,
    )
    budget = ModelCallBudget(1)
    runner = RecordedModelRunner(
        tmp_path / "model.jsonl",
        client,
        budget,
        temperature=0,
        allow_live_model=False,
        run_id="cell-3",
    )

    with pytest.raises(LiveModelCallBlocked):
        runner.call_json(
            "prompt", task="benchmark", agent_id=None, validator=lambda _: []
        )

    assert calls == []
    assert budget.snapshot()["calls_used"] == 0


def test_global_budget_fails_closed_before_extra_call(tmp_path) -> None:
    client = CallableModelClient(lambda prompt, task, agent_id: '{"action":"keep"}')
    budget = ModelCallBudget(1)
    runner = RecordedModelRunner(
        tmp_path / "model.jsonl",
        client,
        budget,
        temperature=0,
        allow_live_model=False,
        run_id="cell-4",
    )
    runner.call_json("first", task="benchmark", agent_id=None, validator=_validator)

    with pytest.raises(ModelCallBudgetExceeded):
        runner.call_json(
            "second", task="benchmark", agent_id=None, validator=_validator
        )

    assert budget.snapshot()["calls_used"] == 1
