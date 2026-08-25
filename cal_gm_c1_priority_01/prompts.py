from __future__ import annotations

import json
from typing import Any

from cal_gm_c1_priority_01.loader import initial_assignments, oracle_plan

RULE = (
    "冲突时高优先级 Agent 必须保持原分配（若该时段仍在其可行集内）；"
    "低优先级 Agent 按其可行集列表顺序选择第一个空闲时段。"
    "禁止把未出现在该 Agent 可行集中的时段分配给该 Agent。"
)


def rule_agent(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return {"assignments": dict(oracle_plan(task, variant))}


def agent_prompt(task: dict[str, Any], variant: str, *, violations: list[dict] | None = None, retry: bool = False) -> str:
    initial = initial_assignments(task, variant)
    a = task["agent_a"]
    b = task["agent_b"][variant]
    evidence = json.dumps(violations or [], ensure_ascii=False)
    head = "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
    body = (
        head
        + '只输出 {"assignments": {"agent_a": "<slot>", "agent_b": "<slot>"}}。\n'
        + "不要输出 conflict 或任何布尔字段。平台只返回违规类型，不会给出正确时段，也不会自动修正。\n"
        + f"【解决规则】{RULE}\n"
        + f"【共同资源】{task['resource_id']}\n"
        + f"【可选时段】{json.dumps(task['slots'], ensure_ascii=False)}\n"
        + "【优先级】agent_a > agent_b\n"
        + f"【初始方案】{json.dumps(initial, ensure_ascii=False)}\n"
        + f"【违规证据】{evidence}\n"
        + f"【Agent A 可行集】{json.dumps(a['feasible'], ensure_ascii=False)}，首选 {a['preferred']}\n"
        + f"【Agent B 可行集】{json.dumps(b['feasible'], ensure_ascii=False)}，首选 {b['preferred']}\n"
    )
    if retry:
        return (
            head
            + '只输出 {"assignments": {"agent_a": "<slot>", "agent_b": "<slot>"}}。\n'
            + "平台拒绝了上一份方案。只返回了违规类型，没有给出正确替代时段。请重试一次。\n"
            + f"【解决规则】{RULE}\n"
            + f"【违规证据】{evidence}\n"
            + f"【初始方案】{json.dumps(initial, ensure_ascii=False)}\n"
            + f"【可选时段】{json.dumps(task['slots'], ensure_ascii=False)}\n"
        )
    return body
