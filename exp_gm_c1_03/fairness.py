from __future__ import annotations

from typing import Any

from exp_gm_c1_03.loader import BANNED, agent_private, leak_tokens_for, load_tasks
from exp_gm_c1_03.loop import ORACLE_MARKERS
from exp_gm_c1_03.prompts import commit_prompt, coordinator_initial_prompt, coordinator_retry_prompt, direct_prompt, report_prompt

CALL_CONTRACT = {
    "direct": ["一次调用看到含保护修订的完整时间线并输出最终联合方案；非正式结果"],
    "multi": [
        "A/B 先交初始报告，Coordinator 形成第一版方案",
        "平台送达登记保护修订，Validator 返回 NACK（intervention 必须进入）",
        "Coordinator 按新 NACK 重提，A/B 自己执行",
    ],
    "drop_protection": [
        "A/B 和 Coordinator 都运行",
        "只丢保护修订，不丢初始报告",
        "control 保护为 no-op 应成功；intervention 应失败",
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
        private_b = agent_private(task, "agent_b", "intervention")
        control_b = agent_private(task, "agent_b", "control")
        tokens = leak_tokens_for(task, "intervention")
        a_prompt = report_prompt(task, "agent_a", private_a, "intervention")
        b_prompt = report_prompt(task, "agent_b", private_b, "intervention")
        init = coordinator_initial_prompt(task, {"agent_a": {"preferred": private_a["preferred"]}}, "intervention")
        retry_on = coordinator_retry_prompt(
            task,
            "intervention",
            reports={"agent_a": {"feasible": private_a["feasible"], "preferred": private_a["preferred"]}, "agent_b": {"feasible": private_b["feasible"], "preferred": private_b["preferred"]}},
            first_plan={"assignments": {"agent_a": task["oracle"]["intervention"]["first"]["agent_a"], "agent_b": task["oracle"]["intervention"]["first"]["agent_b"]}},
            violations=[{"violation": "priority_preservation_violation", "type": "priority_preservation_violation", "agent": "A"}],
            protection_delivered=True,
        )
        retry_off = coordinator_retry_prompt(
            task,
            "intervention",
            reports={"agent_a": {"preferred": private_a["preferred"]}, "agent_b": {"preferred": private_b["preferred"]}},
            first_plan=None,
            violations=[],
            protection_delivered=False,
        )
        commit_a = commit_prompt(task, "agent_a", private_a, None, "intervention", after_protection=False)
        direct = direct_prompt(task, "intervention")
        repair = task["oracle"]["intervention"]["assignments"]["agent_b"]
        for token in tokens:
            if token in a_prompt or token in b_prompt or token in init or token in commit_a or token in retry_off:
                leaks.append({"where": "leaked_protection", "task": task["id"], "token": token})
            if token not in retry_on:
                leaks.append({"where": "retry_missing_protection", "task": task["id"], "token": token})
            if token not in direct:
                leaks.append({"where": "direct_missing_protection", "task": task["id"], "token": token})
        if repair in json_violations_sample():
            leaks.append({"where": "nack_named_repair", "task": task["id"], "token": repair})
        nack_sample = '[{"violation": "priority_preservation_violation", "type": "priority_preservation_violation", "agent": "A", "keep_protected_assignment": true, "forbid_duplicate_claim": true}]'
        if repair in nack_sample:
            leaks.append({"where": "nack_template_has_repair", "task": task["id"], "token": repair})
        if "suggested_slot" in retry_on:
            leaks.append({"where": "retry_suggested_slot", "task": task["id"], "token": "suggested_slot"})
        for marker in ORACLE_MARKERS:
            if marker in a_prompt + b_prompt + init + retry_on + commit_a + direct:
                leaks.append({"where": "oracle", "task": task["id"], "token": marker})
        if control_b["preferred"] == private_b["preferred"]:
            leaks.append({"where": "intervention_not_changed", "task": task["id"], "token": "agent_b"})
        if private_a["feasible"] != agent_private(task, "agent_a", "control")["feasible"]:
            leaks.append({"where": "changed_a_feasible", "task": task["id"], "token": "agent_a"})
        if private_a["preferred"] == task["protection"]["slot"]:
            leaks.append({"where": "intervention_a_prefers_protected", "task": task["id"], "token": "agent_a"})
        if task["phase1"]["control"]["priority"][0] != "agent_a":
            leaks.append({"where": "control_priority", "task": task["id"], "token": "phase1"})
        if task["phase1"]["intervention"]["priority"][0] != "agent_b":
            leaks.append({"where": "intervention_priority", "task": task["id"], "token": "phase1"})
        first = task["oracle"]["intervention"]["first"]
        final = task["oracle"]["intervention"]["assignments"]
        if first == final:
            leaks.append({"where": "intervention_first_equals_final", "task": task["id"], "token": "first"})
        if first["agent_a"] == task["protection"]["slot"]:
            leaks.append({"where": "intervention_first_already_protected", "task": task["id"], "token": "first_a"})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "call_contract": CALL_CONTRACT,
        "logical_calls_per_matrix_cell": 6,
        "environment_rewrites_world": False,
        "coordinator_executes": False,
        "primary_track": "multi",
    }


def json_violations_sample() -> str:
    return '[{"violation":"priority_preservation_violation","agent":"A"}]'
