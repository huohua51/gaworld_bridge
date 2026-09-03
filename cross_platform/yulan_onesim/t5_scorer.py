"""Reuse frozen T5-v3 score math and attach YuLan delivery evidence."""

from __future__ import annotations

from typing import Any

from model_pilot.t5_v3_scorer import score_cell as _score_gaworld_t5

WORKFLOW_ID = "cross_platform_yulan_t5_v3_scope"
SCORER_VERSION = "model-pilot-t5-v3-scope-scorer-v1+yulan-evidence-v1"


def score_cell(**kwargs: Any) -> dict[str, Any]:
    cell = _score_gaworld_t5(**kwargs)
    loop = kwargs["loop"]
    original_id = str(cell["instance_id"])
    run_id = original_id.replace("model_v3_", "yulan_model_v3_", 1)
    cell["workflow_id"] = WORKFLOW_ID
    cell["instance_id"] = run_id
    cell["extra"]["phase"] = "cross_platform_protocol_parity"
    context = cell["extra"]["run_context"]
    context["run_id"] = run_id
    context["environment_version"] = "yulan-onesim-eventbus-9829d722"
    context["trace_version"] = "recipient-verified-policy-and-model-jsonl-v1"
    context["scorer_version"] = SCORER_VERSION
    context["evidence_id"] = f"bundle:{run_id}"
    cell["extra"]["platform"] = "YuLan-OneSim"
    cell["extra"]["platform_evidence"] = {
        "recipient_receipts": str(loop["onesim_receipt_path"]),
        "native_event_flow": str(loop["onesim_event_flow_path"]),
        "native_event_attempts": int(loop["native_event_attempts"]),
        "verified_receipts": int(loop["verified_receipts"]),
        "verified_policy_receipts": int(loop["verified_policy_receipts"]),
        "verified_decision_receipts": int(loop["verified_decision_receipts"]),
        "native_flow_count": int(loop["native_flow_count"]),
        "resident_errors": dict(loop["resident_errors"]),
    }
    return cell


__all__ = ["SCORER_VERSION", "WORKFLOW_ID", "score_cell"]
