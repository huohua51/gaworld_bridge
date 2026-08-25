from __future__ import annotations

from typing import Any

from exp_gm_c1_02.loader import BANNED, agent_baseline, agent_private, leak_tokens_for, load_tasks
from exp_gm_c1_02.loop import ORACLE_MARKERS
from exp_gm_c1_02.prompts import commit_prompt, coordinator_initial_prompt, coordinator_propose_prompt, direct_prompt, report_prompt, revision_prompt

CALL_CONTRACT = {
    "direct": ["一次调用看到双方最新约束并输出唯一联合方案；非正式结果"],
    "multi": [
        "A/B 先交初始报告，Coordinator 形成初始方案",
        "B 发送约束修订",
        "JointAssignmentChannel 只返回违规证据",
        "Coordinator propose_joint_assignment，A/B 自己执行",
    ],
    "drop_revision": [
        "A/B 和 Coordinator 都运行",
        "只丢 B 的最新约束修订，不丢初始报告",
        "control 修订与基线相同，应成功；intervention 应失败",
    ],
    "drop_coordinator": [
        "A/B 信息送达",
        "最终联合方案不交付",
        "Coordinator 不能代执行",
    ],
}


def preflight() -> dict[str, Any]:
    leaks = []
    for task in load_tasks():
        blob = str(task)
        for token in BANNED:
            if token in blob:
                leaks.append({"where": "banned_item", "task": task["id"], "token": token})
        private_a = agent_private(task, "agent_a", "intervention")
        baseline_b = agent_baseline(task, "agent_b")
        rev_b = agent_private(task, "agent_b", "intervention")
        tokens = leak_tokens_for(task, "intervention")
        a_prompt = report_prompt(task, "agent_a", private_a)
        b_base = report_prompt(task, "agent_b", baseline_b)
        b_rev = revision_prompt(task, rev_b)
        init = coordinator_initial_prompt(task, {"agent_a": {"preferred": private_a["preferred"]}})
        propose = coordinator_propose_prompt(task, latest={"agent_a": {"preferred": private_a["preferred"]}}, initial_plan=None, violations=[{"type": "duplicate_resource_claim"}])
        commit_a = commit_prompt(task, "agent_a", private_a, None)
        direct = direct_prompt(task, "intervention")
        for token in tokens:
            if token in a_prompt or token in commit_a or token in b_base or token in init or token in propose:
                leaks.append({"where": "leaked_revision", "task": task["id"], "token": token})
            if token not in b_rev:
                leaks.append({"where": "revision_missing_private", "task": task["id"], "token": token})
            if token not in direct:
                leaks.append({"where": "direct_missing_private", "task": task["id"], "token": token})
        for marker in ORACLE_MARKERS:
            if marker in a_prompt + b_base + b_rev + init + propose + commit_a + direct:
                leaks.append({"where": "oracle", "task": task["id"], "token": marker})
        control_b = agent_private(task, "agent_b", "control")
        if control_b["preferred"] == rev_b["preferred"] and control_b["feasible"] == rev_b["feasible"]:
            leaks.append({"where": "intervention_not_changed", "task": task["id"], "token": "agent_b"})
        if private_a["feasible"] != agent_private(task, "agent_a", "control")["feasible"]:
            leaks.append({"where": "changed_a", "task": task["id"], "token": "agent_a"})
        if baseline_b["preferred"] != control_b["preferred"]:
            leaks.append({"where": "baseline_not_control", "task": task["id"], "token": "baseline"})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "call_contract": CALL_CONTRACT,
        "logical_calls_per_matrix_cell": 7,
        "environment_rewrites_world": False,
        "coordinator_executes": False,
        "primary_track": "multi",
    }
