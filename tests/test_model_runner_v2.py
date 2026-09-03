"""Tests for the budgeted evidence-first model runner."""

from __future__ import annotations

import json

import pytest

from benchmark_core.model_runner_v2 import (
    CallableModelClient,
    LiveModelCallBlocked,
    ModelCallBudget,
    ModelCallBudgetExceeded,
    ModelClientInfo,
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


def test_runner_can_auditably_normalize_one_whole_json_fence(tmp_path) -> None:
    client = CallableModelClient(
        lambda prompt, task, agent_id: '```json\n{"action":"keep"}\n```'
    )
    path = tmp_path / "model.jsonl"
    runner = RecordedModelRunner(
        path,
        client,
        ModelCallBudget(1),
        temperature=0,
        allow_live_model=False,
        run_id="cell-fenced",
        json_normalization="single_json_fence",
    )

    response = runner.call_json(
        "prompt", task="benchmark", agent_id="reviewer", validator=_validator
    )
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    recorded = rows[-1]

    assert response.ok is True
    assert response.parsed == {"action": "keep"}
    assert response.normalization_applied is True
    assert response.normalization_rule == "whole_response_single_json_fence_v1"
    assert recorded["raw_response"].startswith("```json")
    assert recorded["normalized_response"] == '{"action":"keep"}'
    assert recorded["normalization_applied"] is True


@pytest.mark.parametrize(
    "raw",
    [
        'prefix\n```json\n{"action":"keep"}\n```',
        '```json\n{"action":"keep"}\n```\nsuffix',
        '```\n{"action":"keep"}\n```',
        '```json\n{"action":"keep"}\n```\n```json\n{}\n```',
    ],
)
def test_conservative_normalizer_rejects_non_exact_fences(tmp_path, raw) -> None:
    runner = RecordedModelRunner(
        tmp_path / "model.jsonl",
        CallableModelClient(lambda prompt, task, agent_id: raw),
        ModelCallBudget(1),
        temperature=0,
        allow_live_model=False,
        run_id="cell-non-exact-fence",
        json_normalization="single_json_fence",
    )

    response = runner.call_json(
        "prompt", task="benchmark", agent_id=None, validator=_validator
    )

    assert response.ok is False
    assert response.normalization_applied is False
    assert "json_parse_error" in response.error


class _AuditedClient:
    info = ModelClientInfo("audited-provider", "audited-v1", False)

    def __init__(self) -> None:
        self.metadata: dict[str, object] = {}

    def generate(self, prompt: str, *, task: str, agent_id: str | None) -> str:
        self.metadata = {
            "router_call_id": "router-1",
            "selected_provider": "primary",
            "provider_calls": [
                {
                    "provider": "primary",
                    "fallback_index": 0,
                    "success": True,
                    "latency_ms": 3,
                    "secret_should_be_dropped": "nope",
                }
            ],
            "transport_attempts": [
                {
                    "attempt": 1,
                    "max_attempts": 2,
                    "success": False,
                    "retryable": True,
                    "will_retry": True,
                    "error_type": "ConnectionError",
                    "error_message": "tls eof",
                    "api_key": "must-not-be-recorded",
                },
                {
                    "attempt": 2,
                    "max_attempts": 2,
                    "success": True,
                    "retryable": False,
                    "will_retry": False,
                    "error_type": "",
                    "error_message": "",
                },
            ],
        }
        return '{"action":"keep"}'

    def consume_last_call_metadata(self) -> dict[str, object]:
        metadata = self.metadata
        self.metadata = {}
        return metadata


def test_runner_records_transport_attempts_under_logical_call(tmp_path) -> None:
    path = tmp_path / "model.jsonl"
    budget = ModelCallBudget(1)
    runner = RecordedModelRunner(
        path,
        _AuditedClient(),
        budget,
        temperature=0,
        allow_live_model=False,
        run_id="cell-audit",
    )

    response = runner.call_json(
        "prompt", task="benchmark", agent_id=None, validator=_validator
    )
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    attempts = [row for row in rows if row["event"] == "model_transport_attempt"]

    assert response.ok is True
    assert [row["attempt"] for row in attempts] == [1, 2]
    assert all(row["call_id"] == "cell-audit:call-1" for row in attempts)
    assert all("api_key" not in row for row in attempts)
    assert all("error_message" not in row for row in attempts)
    assert "secret_should_be_dropped" not in rows[-1]["provider_calls"][0]
    assert budget.snapshot()["calls_used"] == 1
    assert budget.snapshot()["transport_attempts_observed"] == 2
    assert budget.snapshot()["transport_retries_observed"] == 1
    assert runner.summary()["transport_retries_observed"] == 1


def test_provider_exception_text_is_not_written_to_evidence(tmp_path) -> None:
    secret = "credential-like-secret"

    def fail(prompt: str, task: str, agent_id: str | None) -> str:
        raise RuntimeError(secret)

    path = tmp_path / "model.jsonl"
    runner = RecordedModelRunner(
        path,
        CallableModelClient(fail),
        ModelCallBudget(1),
        temperature=0,
        allow_live_model=False,
        run_id="cell-provider-error",
    )

    response = runner.call_json(
        "prompt", task="benchmark", agent_id=None, validator=_validator
    )

    assert response.ok is False
    assert response.error == "provider_error:RuntimeError"
    assert secret not in path.read_text(encoding="utf-8")


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
