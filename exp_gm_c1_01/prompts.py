"""C1-01 prompts. Hidden oracle never enters prompts."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_c1_01.contract import PLAN_VERSION
from exp_gm_c1_01.loader import agent_private, oracle_plan, public_spec


def rule_report(task: dict[str, Any], agent_id: str, variant: str) -> dict[str, Any]:
    private = agent_private(task, agent_id, variant)
    return {"agent_id": agent_id, "feasible": list(private["feasible"]), "preferred": private["preferred"]}


def rule_plan(task: dict[str, Any], variant: str, reports: dict[str, dict[str, Any]], *, global_view: bool) -> dict[str, Any]:
    if global_view:
        return oracle_plan(task, variant)
    if "agent_a" not in reports or "agent_b" not in reports:
        assignments = {agent_id: payload.get("preferred") for agent_id, payload in reports.items()}
        return {
            "plan_version": PLAN_VERSION,
            "conflict": False,
            "assignments": assignments,
            "rule": task["rule"],
            "resource_id": task["resource_id"],
        }
    occupied: set[str] = set()
    assignments: dict[str, str] = {}
    for agent_id in task["priority"]:
        report = reports[agent_id]
        feasible = list(report.get("feasible") or [])
        preferred = str(report.get("preferred") or "")
        if preferred in feasible and preferred not in occupied:
            slot = preferred
        else:
            slot = next((item for item in feasible if item not in occupied), "")
        assignments[agent_id] = slot
        if slot:
            occupied.add(slot)
    preferred_hit = str(reports["agent_a"].get("preferred")) == str(reports["agent_b"].get("preferred"))
    return {
        "plan_version": PLAN_VERSION,
        "conflict": preferred_hit,
        "assignments": assignments,
        "rule": task["rule"],
        "resource_id": task["resource_id"],
    }


def rule_commit(task: dict[str, Any], agent_id: str, variant: str, plan: dict[str, Any] | None) -> dict[str, Any]:
    private = agent_private(task, agent_id, variant)
    if not plan:
        return {"agent_id": agent_id, "plan_version": "", "confirm": False, "slot": None}
    slot = str((plan.get("assignments") or {}).get(agent_id) or "")
    ok = bool(slot) and slot in private["feasible"] and str(plan.get("plan_version") or "") == PLAN_VERSION
    return {
        "agent_id": agent_id,
        "plan_version": str(plan.get("plan_version") or ""),
        "confirm": ok,
        "slot": slot if ok else None,
    }


def rule_direct(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return oracle_plan(task, variant)


def _spec_block(task: dict[str, Any]) -> str:
    spec = public_spec(task)
    return (
        f"【共同资源】{spec['resource_id']} 同一时段只能被一个 Agent 占用。\n"
        f"【可选时段】{json.dumps(spec['slots'], ensure_ascii=False)}\n"
        f"【优先级】{' > '.join(spec['priority'])}\n"
        f"【解决规则】{spec['rule_text']}\n"
        "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
    )


def report_prompt(task: dict[str, Any], agent_id: str, private: dict[str, Any], *, peer_private: dict[str, Any] | None) -> str:
    extra = ""
    if peer_private:
        extra = "你能看到双方约束，但这一步只报告你自己的可行集和首选。\n" + f"【双方约束】{json.dumps({'self': private, 'peer': peer_private}, ensure_ascii=False)}\n"
    else:
        extra = "只能根据你自己的私有约束报告。不要编造对方约束。\n" + f"【你的私有约束】{json.dumps(private, ensure_ascii=False)}\n"
    return (
        _spec_block(task)
        + f"你是 {agent_id}。输出 {{\"agent_id\": \"{agent_id}\", \"feasible\": [...], \"preferred\": \"<slot>\"}}。\n"
        + extra
    )


def coordinator_prompt(task: dict[str, Any], reports: dict[str, dict[str, Any]], *, global_view: bool, both_private: dict[str, Any] | None) -> str:
    body = (
        _spec_block(task)
        + "你是协调者。根据已有信息检测冲突，并按登记规则生成联合分配。\n"
        '输出 {"plan_version": "plan-001", "conflict": true或false, "assignments": {"agent_a": "<slot>", "agent_b": "<slot>"}, "rule": "priority_keep_then_earliest_free"}。\n'
        "conflict 在双方首选相同时为 true，否则 false。不要把两人分到同一时段。\n"
        f"【已送达约束报告】{json.dumps(reports, ensure_ascii=False)}\n"
    )
    if global_view and both_private:
        body += "你持有双方完整私有约束，即使某份报告缺失也必须按规则给出唯一方案。\n"
        body += f"【双方私有约束】{json.dumps(both_private, ensure_ascii=False)}\n"
    else:
        body += "只能使用已送达报告。不要编造未送达 Agent 的可行集。\n"
    return body


def commit_prompt(task: dict[str, Any], agent_id: str, private: dict[str, Any], plan: dict[str, Any] | None) -> str:
    return (
        _spec_block(task)
        + f"你是 {agent_id}。确认联合方案中分配给你的时段，并占用该时段。\n"
        '输出 {"agent_id": "'
        + agent_id
        + '", "plan_version": "plan-001", "confirm": true或false, "slot": "<slot或null>"}。\n'
        "分配不在你的可行集内、方案缺失或版本不一致时 confirm=false。\n"
        f"【你的私有约束】{json.dumps(private, ensure_ascii=False)}\n"
        f"【联合方案】{json.dumps(plan, ensure_ascii=False)}\n"
    )


def direct_prompt(task: dict[str, Any], variant: str) -> str:
    both = {
        "agent_a": agent_private(task, "agent_a", variant),
        "agent_b": agent_private(task, "agent_b", variant),
    }
    return (
        _spec_block(task)
        + "你看到双方完整约束。直接给出唯一联合方案。\n"
        '输出 {"plan_version": "plan-001", "conflict": true或false, "assignments": {"agent_a": "<slot>", "agent_b": "<slot>"}, "rule": "priority_keep_then_earliest_free"}。\n'
        f"【双方私有约束】{json.dumps(both, ensure_ascii=False)}\n"
    )
