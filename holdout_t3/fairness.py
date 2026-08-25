from __future__ import annotations

from typing import Any

from exp_gm_t3_01.fairness import sha256_text
from holdout_t3.artifacts import render_source
from holdout_t3.loader import leak_tokens_for, load_tasks
from holdout_t3.prompts import draft_prompt, executor_prompt, reviewer_prompt

ORACLE_MARKERS = (
    "test_t303_",
    "test_parking_",
    "test_deposit_",
    "test_queue_",
    "hidden test",
    "test_oracle",
)

CALL_CONTRACT = {
    "direct": [
        "Builder 生成初稿；提示不得含 Intervention 值",
        "决策者读取私有最终标准并判断 keep/update",
        "同一 Agent 按 APPLY-01 修改或确认",
    ],
    "single": [
        "Builder 生成初稿；提示不得含 Intervention 值",
        "同一 Agent 只按公开 v1 简报自检，看不到私有核验信息",
        "同一 Agent 按 APPLY-01 修改或确认",
    ],
    "multi": [
        "Builder 生成初稿",
        "独立 Reviewer 读取私有最终标准并输出决定",
        "IntegrityMailbox 原样传递",
        "Executor 按 APPLY-01 修改或确认",
    ],
    "drop": [
        "Builder 生成初稿",
        "Reviewer 读取私有最终标准并正常输出",
        "通道丢弃消息",
        "Executor 收到空消息并提交",
    ],
}


def oracle_in_prompt(prompt: str) -> list[str]:
    return [tok for tok in ORACLE_MARKERS if tok in (prompt or "")]


def v2_leaks_in_prompt(task: dict[str, Any], prompt: str) -> list[str]:
    return [tok for tok in leak_tokens_for(task, "intervention") if tok and tok in (prompt or "")]


def call_kinds_ok(kinds: list[str]) -> bool:
    return list(kinds) == ["builder_draft", "review", "builder_final"]


def preflight() -> dict[str, Any]:
    leaks = []
    for task in load_tasks():
        first = draft_prompt(task)
        drop_final = executor_prompt('SPEC_VERSION = "v1"\n', None)
        for token in leak_tokens_for(task, "intervention"):
            if token in first:
                leaks.append({"where": "first_call", "task": task["id"], "token": token})
            if token in drop_final:
                leaks.append({"where": "drop_final", "task": task["id"], "token": token})
        for marker in ORACLE_MARKERS:
            if marker in first or marker in drop_final:
                leaks.append({"where": "oracle", "task": task["id"], "token": marker})
        draft = render_source(task, "v1")
        self_p = reviewer_prompt(task, "intervention", draft, private_visible=False, self_check=True)
        rev_p = reviewer_prompt(task, "intervention", draft, private_visible=True, self_check=False)
        direct_p = reviewer_prompt(task, "intervention", draft, private_visible=True, self_check=True)
        if "自检" not in self_p or "审核员" not in rev_p:
            leaks.append({"where": "role_split", "task": task["id"], "token": "self_check_vs_reviewer"})
        if v2_leaks_in_prompt(task, self_p):
            leaks.append({"where": "single_self_check", "task": task["id"], "token": "private_v2"})
        if not v2_leaks_in_prompt(task, rev_p):
            leaks.append({"where": "multi_reviewer", "task": task["id"], "token": "missing_private_v2"})
        if not v2_leaks_in_prompt(task, direct_p):
            leaks.append({"where": "direct", "task": task["id"], "token": "missing_private_v2"})
        if any(marker in self_p or marker in rev_p or marker in direct_p for marker in ORACLE_MARKERS):
            leaks.append({"where": "oracle", "task": task["id"], "token": "reviewer_oracle"})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "call_contract": CALL_CONTRACT,
        "hidden_oracle_in_prompts": False,
        "environment_rewrites_files": False,
        "channel_rewrites_payload": False,
        "logical_calls_per_cell": 3,
        "single_lacks_private_v2": True,
        "reviewer_has_private_v2": True,
        "v2_leaks_helper": v2_leaks_in_prompt,
        "sha256_text": sha256_text,
    }
