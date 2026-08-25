from __future__ import annotations

from typing import Any

from exp_gm_t3_01.fairness import ORACLE_MARKERS, sha256_text, v2_leaks_in_prompt
from exp_gm_t3_01.artifacts import render_source
from exp_gm_t3_01.loader import leak_tokens_for, load_tasks
from exp_gm_t3_02.prompts import draft_prompt, executor_prompt, reviewer_prompt

CALL_CONTRACT = {
    "single": [
        "Builder 生成初稿",
        "同一 Agent 按 CHANGE-01 判断 keep/update",
        "同一 Agent 按 APPLY-01 修改或确认",
    ],
    "multi": [
        "Builder 生成初稿",
        "独立 Reviewer 按 CHANGE-01 输出决定",
        "IntegrityMailbox 原样传递",
        "Executor 按 APPLY-01 修改或确认",
    ],
    "drop": [
        "Builder 生成初稿",
        "Reviewer 正常输出完整决定",
        "通道丢弃消息",
        "Executor 收到空消息并提交",
    ],
}


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
        self_p = reviewer_prompt(task, "intervention", draft, self_check=True)
        rev_p = reviewer_prompt(task, "intervention", draft, self_check=False)
        if "自检" not in self_p or "审核员" not in rev_p:
            leaks.append({"where": "role_split", "task": task["id"], "token": "self_check_vs_reviewer"})
        if "test_parking_" in self_p or "test_parking_" in rev_p:
            leaks.append({"where": "oracle", "task": task["id"], "token": "reviewer_oracle"})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "call_contract": CALL_CONTRACT,
        "hidden_oracle_in_prompts": False,
        "environment_rewrites_files": False,
        "channel_rewrites_payload": False,
        "logical_calls_per_cell": 3,
        "v2_leaks_helper": v2_leaks_in_prompt,
        "sha256_text": sha256_text,
    }
