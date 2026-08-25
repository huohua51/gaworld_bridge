"""Development tasks plus read-only fact specs. No held-out names in prompts."""

from __future__ import annotations

from exp_gm_04c.tasks import TASKS, leak_tokens_for, private_payload as _private

FACT_SPECS = {
    "w1_wage_gate": [
        {"symbol": "SPEC_VERSION", "criterion_path": "spec_version", "parse": "str"},
        {"symbol": "THRESHOLD", "criterion_path": "reservation_wage", "parse": "int"},
    ],
    "w1_return_floor": [
        {"symbol": "SPEC_VERSION", "criterion_path": "spec_version", "parse": "str"},
        {"symbol": "RATE", "criterion_path": "min_return_rate", "parse": "float"},
    ],
    "w1_budget_remaining": [
        {"symbol": "SPEC_VERSION", "criterion_path": "spec_version", "parse": "str"},
        {"symbol": "BUDGET", "criterion_path": "total_budget", "parse": "int"},
    ],
}


def private_payload(task: dict, version: str, *, protocol: str) -> dict:
    payload = _private(task, version)
    if protocol == "evidence_bound":
        required = dict(payload["required_change"])
        required["spec_version"] = version
        payload["required_change"] = required
        payload["instruction"] = (
            "根据私有标准和只读事实判断草稿是否满足登记要求。"
            "满足则 approve 且 mismatches 为空；否则 revise，且每条 mismatch 必须绑定 fact_id。"
            "不要改文件。"
        )
    return payload


__all__ = ["FACT_SPECS", "TASKS", "leak_tokens_for", "private_payload"]
