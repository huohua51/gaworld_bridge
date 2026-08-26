"""One-call live-provider smoke test with strict JSON evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from benchmark_core.model_runner import (
    GAWorldModelClient,
    ModelCallBudget,
    ModelClient,
    RecordedModelRunner,
)
from v0_first_batch.paths import BRIDGE_ROOT, ensure_import_paths


def _validator(payload: dict[str, Any]) -> list[str]:
    return (
        []
        if set(payload) == {"status"} and payload.get("status") == "ok"
        else ["status_must_equal_ok"]
    )


def run_smoke(
    out: Path,
    client: ModelClient,
    *,
    temperature: float,
    allow_live_model: bool,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    budget = ModelCallBudget(1, max_response_chars=2_000)
    runner = RecordedModelRunner(
        out / "model_trace.jsonl",
        client,
        budget,
        temperature=temperature,
        allow_live_model=allow_live_model,
        run_id="provider-smoke",
    )
    prompt = json.dumps(
        {
            "protocol": "gaworld-benchmark-paid-smoke-v1",
            "instruction": (
                "Return exactly one JSON object with one field: status must equal ok. "
                "Do not use markdown."
            ),
            "response_schema": {"status": "ok"},
        },
        separators=(",", ":"),
    )
    response = runner.call_json(
        prompt,
        task="benchmark_smoke",
        agent_id=None,
        validator=_validator,
    )
    result = {
        "smoke_id": "gaworld-benchmark-paid-smoke-v1",
        "ok": response.ok,
        "error": response.error,
        "provider": client.info.provider,
        "model_version": client.info.model_version,
        "live_model": client.info.live,
        "temperature": temperature,
        "ranking_eligible": False,
        "evidence_path": str(out / "model_trace.jsonl"),
        "budget": budget.snapshot(),
    }
    (out / "SMOKE_RESULT.yaml").write_text(
        yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--allow-live-model", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument(
        "--out", type=Path, default=BRIDGE_ROOT / "output" / "model_pilot_live_smoke_v1"
    )
    args = parser.parse_args()
    if not args.allow_live_model:
        parser.error("live model smoke test requires --allow-live-model")
    ensure_import_paths()
    client = GAWorldModelClient(
        args.provider,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    result = run_smoke(
        args.out,
        client,
        temperature=args.temperature,
        allow_live_model=True,
    )
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
