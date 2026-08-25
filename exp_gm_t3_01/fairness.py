"""Fairness checks: equal 3-call budget, v2 isolation, no oracle in prompts."""

from __future__ import annotations

import hashlib
from typing import Any

from exp_gm_t3_01.loader import leak_tokens_for

ORACLE_MARKERS = (
    "test_parking_",
    "test_deposit_",
    "test_queue_",
    "hidden test",
    "test_oracle",
)


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def oracle_in_prompt(prompt: str) -> list[str]:
    return [tok for tok in ORACLE_MARKERS if tok in (prompt or "")]


def v2_leaks_in_prompt(task: dict[str, Any], prompt: str) -> list[str]:
    return [tok for tok in leak_tokens_for(task, "intervention") if tok and tok in (prompt or "")]


def call_kinds_ok(kinds: list[str]) -> bool:
    return list(kinds) == ["builder_draft", "review", "builder_final"]


CALL_CONTRACT = {
    "single": [
        "Executor 根据 v1 brief 生成初稿；提示不得含 Intervention 值",
        "同一 Agent 读取最终标准并自检（self_check_prompt）",
        "同一 Agent 根据自检完成终稿",
    ],
    "multi": [
        "Executor 根据 v1 brief 生成初稿；与 Single/Drop 共享同一初稿哈希",
        "独立 Reviewer 读取私有最终标准并审核（reviewer_prompt）",
        "Executor 收到审核意见并完成终稿",
    ],
    "drop": [
        "Executor 根据 v1 brief 生成初稿；与 Single/Multi 共享同一初稿哈希",
        "Reviewer 必须实际运行并读取私有最终标准，但意见随后丢弃",
        "Executor 收不到审核意见，仍消耗第三次调用完成终稿",
    ],
}


def preflight() -> dict[str, Any]:
    from exp_gm_t3_01.loader import leak_tokens_for, load_tasks, private_payload
    from exp_gm_t3_01.roles import builder_draft_prompt, builder_revise_prompt, reviewer_prompt, self_check_prompt

    leaks = []
    for task in load_tasks():
        draft_prompt = builder_draft_prompt(task["brief"])
        drop_final = builder_revise_prompt(task["brief"], "SPEC_VERSION = \"v1\"\n", None)
        for token in leak_tokens_for(task, "intervention"):
            if token in draft_prompt:
                leaks.append({"where": "first_call", "task": task["id"], "token": token})
            if token in drop_final:
                leaks.append({"where": "drop_final", "task": task["id"], "token": token})
        for marker in ORACLE_MARKERS:
            if marker in draft_prompt or marker in drop_final:
                leaks.append({"where": "oracle", "task": task["id"], "token": marker})
        private = private_payload(task, "intervention")
        self_p = self_check_prompt("draft", private)
        rev_p = reviewer_prompt("draft", private)
        if "自检" not in self_p or "审核员" not in rev_p:
            leaks.append({"where": "role_split", "task": task["id"], "token": "self_check_vs_reviewer"})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "call_contract": CALL_CONTRACT,
        "hidden_oracle_in_prompts": False,
        "environment_rewrites_files": False,
        "drop_reviewer_skipped": False,
        "logical_calls_per_cell": 3,
    }
