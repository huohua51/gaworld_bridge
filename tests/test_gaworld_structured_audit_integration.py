"""Cross-repository structured-output and transport-audit integration test."""

from __future__ import annotations

import json
from unittest.mock import Mock

from benchmark_core.model_runner_v2 import (
    GAWorldModelClient,
    ModelCallBudget,
    RecordedModelRunner,
)
from v0_first_batch.paths import ensure_import_paths


def test_gaworld_client_connects_native_json_audit_and_fence_fallback(
    tmp_path, monkeypatch
) -> None:
    ensure_import_paths()
    monkeypatch.setenv("PARATERA_API_KEY", "integration-test-key")
    import llm_providers

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": '```json\n{"action":"keep"}\n```'}}]
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(llm_providers.requests, "post", post)

    client = GAWorldModelClient(
        "paratera_glm",
        temperature=0,
        max_tokens=64,
        response_format={"type": "json_object"},
        retry_attempts=1,
    )
    trace = tmp_path / "model.jsonl"
    runner = RecordedModelRunner(
        trace,
        client,
        ModelCallBudget(1),
        temperature=0,
        allow_live_model=True,
        run_id="integration",
        json_normalization="single_json_fence",
    )

    result = runner.call_json(
        "return json",
        task="integration",
        agent_id="reviewer",
        validator=lambda payload: (
            [] if payload.get("action") == "keep" else ["bad_action"]
        ),
    )
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]

    assert result.ok is True
    assert result.normalization_applied is True
    assert post.call_count == 1
    assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}
    assert [row["event"] for row in rows] == [
        "model_request",
        "model_transport_attempt",
        "model_response",
    ]
    assert rows[1]["attempt"] == 1
    assert rows[1]["max_attempts"] == 1
    assert rows[1]["success"] is True
    assert rows[2]["transport_attempt_count"] == 1
    assert rows[2]["transport_retry_count"] == 0
    assert "integration-test-key" not in trace.read_text(encoding="utf-8")
