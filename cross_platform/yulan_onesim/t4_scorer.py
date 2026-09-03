"""Reuse the frozen T4-v2 score calculation with YuLan evidence metadata."""

from __future__ import annotations

from typing import Any

from model_pilot.t4_v2_scorer import score_cell as _score_gaworld_t4

WORKFLOW_ID = "cross_platform_yulan_t4_v2"
SCORER_VERSION = "model-pilot-t4-v2-scorer-v1+yulan-evidence-v1"


def score_cell(**kwargs: Any) -> dict[str, Any]:
    cell = _score_gaworld_t4(**kwargs)
    loop = kwargs["loop"]
    cell["workflow_id"] = WORKFLOW_ID
    cell["extra"]["phase"] = "cross_platform_protocol_parity"
    context = cell["extra"]["run_context"]
    context["environment_version"] = "yulan-onesim-eventbus-9829d722"
    context["trace_version"] = "recipient-verified-network-and-model-jsonl-v1"
    context["scorer_version"] = SCORER_VERSION
    cell["extra"]["platform"] = "YuLan-OneSim"
    cell["extra"]["platform_evidence"] = {
        "recipient_receipts": str(loop["onesim_receipt_path"]),
        "native_event_flow": str(loop["onesim_event_flow_path"]),
        "native_event_attempts": int(loop["native_event_attempts"]),
        "verified_receipts": int(loop["verified_receipts"]),
    }
    return cell


__all__ = ["SCORER_VERSION", "WORKFLOW_ID", "score_cell"]

