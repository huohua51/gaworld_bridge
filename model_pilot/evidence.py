"""Independent JSONL evidence readers for model pilots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: str) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.is_file() or target.stat().st_size == 0:
        return []
    return [
        json.loads(line)
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def model_trace_evidence(path: str) -> dict[str, Any]:
    rows = read_jsonl(path)
    requests = [row for row in rows if row.get("event") == "model_request"]
    responses = [row for row in rows if row.get("event") == "model_response"]
    request_ids = {str(row.get("call_id") or "") for row in requests}
    response_ids = {str(row.get("call_id") or "") for row in responses}
    contract_ok = (
        bool(requests)
        and len(requests) == len(responses)
        and request_ids == response_ids
        and all(row.get("ok") is True for row in responses)
    )
    first = requests[0] if requests else {}
    return {
        "rows": rows,
        "requests": requests,
        "responses": responses,
        "trace_parseable": bool(rows),
        "contract_ok": contract_ok,
        "calls": len(requests),
        "provider": str(first.get("provider") or "unknown"),
        "model_version": str(first.get("model_version") or "unknown"),
        "temperature": float(first.get("temperature") or 0.0),
        "evidence_ids": [
            str(row.get("evidence_id") or "")
            for row in responses
            if row.get("evidence_id")
        ],
        "errors": [
            str(error) for row in responses for error in (row.get("errors") or [])
        ],
    }


__all__ = ["model_trace_evidence", "read_jsonl"]
