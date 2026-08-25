from __future__ import annotations

import json
from typing import Any

from cal_gm_c1_repair_01.contract import A_KEY, B_KEY
from cal_gm_c1_repair_01.loader import initial_assignments, oracle_value, solve_reallocate
from gaworld.work.coordination import occupancy_table


def rule_agent(task: dict[str, Any], variant: str) -> dict[str, Any]:
    component = task["component"]
    if component == "A":
        return {A_KEY: bool(oracle_value(task, variant))}
    if component == "B":
        return {B_KEY: bool(oracle_value(task, variant))}
    return {"assignments": dict(solve_reallocate(task, variant))}


def agent_prompt(task: dict[str, Any], variant: str, *, violations: list[dict] | None = None, retry: bool = False) -> str:
    component = task["component"]
    head = "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
    if component == "A":
        a = task["agent_a"]
        b = task["agent_b"][variant]
        return (
            head
            + f'只输出 {{"{A_KEY}": true 或 false}}。不要输出 assignments 或其它字段。\n'
            + "判断的是调整前的初始方案：两个 Agent 最初选择的资源与时段是否相同。\n"
            + "同一资源且同一时段为 true；资源或时段不同为 false。\n"
            + f"【Agent A 初始选择】资源 {a['resource']}，时段 {a['slot']}\n"
            + f"【Agent B 初始选择】资源 {b['resource']}，时段 {b['slot']}\n"
        )
    if component == "B":
        plan = task["final"][variant]
        occ = occupancy_table(plan)
        return (
            head
            + f'只输出 {{"{B_KEY}": true 或 false}}。不要输出 assignments 或其它字段。\n'
            + "判断已经形成的最终占用表：是否仍有两个 Agent 占用同一时段。\n"
            + "没有重复占用为 true；仍有重复占用为 false。这不是初始冲突判断。\n"
            + "占用表是观察事实，不是标准答案。\n"
            + f"【最终方案】{json.dumps(plan, ensure_ascii=False)}\n"
            + f"【占用表】{json.dumps(occ, ensure_ascii=False)}\n"
            + f"【共同资源】{task['resource_id']}\n"
        )
    initial = initial_assignments(task, variant)
    a = task["agent_a"]
    b = task["agent_b"][variant]
    evidence = json.dumps(violations or [], ensure_ascii=False)
    if retry:
        return (
            head
            + '只输出 {"assignments": {"agent_a": "<slot>", "agent_b": "<slot>"}}。\n'
            + "不要输出 conflict、initial_conflict_detected、final_plan_conflict_free 或任何布尔字段。\n"
            + "平台只返回违规证据，不会给出正确时段，也不会自动修正。\n"
            + "请重新提交联合分配。高优先级 Agent 保留原时段；低优先级 Agent 使用最早可行空闲时段。\n"
            + f"【违规证据】{evidence}\n"
            + f"【初始方案】{json.dumps(initial, ensure_ascii=False)}\n"
            + f"【可选时段】{json.dumps(task['slots'], ensure_ascii=False)}\n"
        )
    return (
        head
        + '只输出 {"assignments": {"agent_a": "<slot>", "agent_b": "<slot>"}}。\n'
        + "不要输出 conflict、initial_conflict_detected、final_plan_conflict_free 或任何布尔字段。\n"
        + "平台只返回违规证据，不会给出正确时段，也不会自动修正。必须提交 propose_joint_assignment 对应的 assignments。\n"
        + "高优先级 Agent 保留原时段；低优先级 Agent 使用最早可行空闲时段。\n"
        + f"【初始方案】{json.dumps(initial, ensure_ascii=False)}\n"
        + f"【违规证据】{evidence}\n"
        + f"【可选时段】{json.dumps(task['slots'], ensure_ascii=False)}\n"
        + "【优先级】agent_a > agent_b\n"
        + f"【Agent A】可行 {json.dumps(a['feasible'], ensure_ascii=False)}，首选 {a['preferred']}\n"
        + f"【Agent B】可行 {json.dumps(b['feasible'], ensure_ascii=False)}，首选 {b['preferred']}\n"
    )
