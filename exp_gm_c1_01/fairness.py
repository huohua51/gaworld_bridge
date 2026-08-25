from __future__ import annotations

from typing import Any

from exp_gm_c1_01.loader import agent_private, leak_tokens_for, load_tasks
from exp_gm_c1_01.loop import ORACLE_MARKERS
from exp_gm_c1_01.prompts import commit_prompt, coordinator_prompt, direct_prompt, report_prompt

CALL_CONTRACT = {
    "direct": ["一次调用看到双方约束并输出唯一联合方案"],
    "single": [
        "同一 Agent 看到双方约束",
        "仍走 5 次调用：A报告、B报告、协调、A确认执行、B确认执行",
    ],
    "multi": [
        "A/B 各持私有约束并发送报告",
        "协调者只读已送达报告",
        "两人确认同一方案版本并占用资源",
    ],
    "drop": [
        "A/B 和协调者都运行",
        "B 的约束报告被丢弃",
        "协调者收件箱没有 B",
    ],
}


def preflight() -> dict[str, Any]:
    leaks = []
    for task in load_tasks():
        private_a = agent_private(task, "agent_a", "intervention")
        private_b = agent_private(task, "agent_b", "intervention")
        tokens = leak_tokens_for(task, "intervention")
        a_prompt = report_prompt(task, "agent_a", private_a, peer_private=None)
        b_prompt = report_prompt(task, "agent_b", private_b, peer_private=None)
        coord = coordinator_prompt(task, {"agent_a": {"agent_id": "agent_a", "feasible": private_a["feasible"], "preferred": private_a["preferred"]}}, global_view=False, both_private=None)
        commit_a = commit_prompt(task, "agent_a", private_a, None)
        direct = direct_prompt(task, "intervention")
        for token in tokens:
            if token in a_prompt or token in commit_a:
                leaks.append({"where": "agent_a", "task": task["id"], "token": token})
            if token in coord:
                leaks.append({"where": "drop_coordinator", "task": task["id"], "token": token})
            if token not in b_prompt:
                leaks.append({"where": "agent_b_missing_private", "task": task["id"], "token": token})
            if token not in direct:
                leaks.append({"where": "direct_missing_private", "task": task["id"], "token": token})
            if token not in str(private_b):
                leaks.append({"where": "private_payload", "task": task["id"], "token": token})
        for marker in ORACLE_MARKERS:
            if marker in a_prompt + b_prompt + coord + commit_a + direct:
                leaks.append({"where": "oracle", "task": task["id"], "token": marker})
        control_b = agent_private(task, "agent_b", "control")
        interv_b = agent_private(task, "agent_b", "intervention")
        if control_b["feasible"] == interv_b["feasible"] and control_b["preferred"] == interv_b["preferred"]:
            leaks.append({"where": "intervention_not_changed", "task": task["id"], "token": "agent_b"})
        if private_a["feasible"] != agent_private(task, "agent_a", "control")["feasible"]:
            leaks.append({"where": "control_intervention_changed_a", "task": task["id"], "token": "agent_a"})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "call_contract": CALL_CONTRACT,
        "logical_calls_per_matrix_cell": 5,
        "environment_rewrites_world": False,
        "channel_rewrites_payload": False,
    }
