"""C1-02 prompts. Oracle never enters prompts. No vague conflict field."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_c1_02.contract import INITIAL_VERSION, PLAN_VERSION, RULE_ID
from exp_gm_c1_02.loader import agent_baseline, agent_private, oracle_plan, public_spec, solve_from_privates


def _spec_block(task: dict[str, Any]) -> str:
    spec = public_spec(task)
    return (
        f"【共同资源】{spec['resource_id']} 同一时段只能被一个 Agent 占用。\n"
        f"【可选时段】{json.dumps(spec['slots'], ensure_ascii=False)}\n"
        f"【优先级】{' > '.join(spec['priority'])}\n"
        f"【解决规则】{spec['rule_text']}\n"
        "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
    )


def rule_report(task: dict[str, Any], agent_id: str, *, baseline: bool) -> dict[str, Any]:
    private = agent_baseline(task, agent_id) if baseline else agent_private(task, agent_id, "intervention")
    if agent_id == "agent_a":
        private = agent_private(task, "agent_a", "control")
    return {"agent_id": agent_id, "feasible": list(private["feasible"]), "preferred": private["preferred"]}


def rule_revision(task: dict[str, Any], variant: str) -> dict[str, Any]:
    private = agent_private(task, "agent_b", variant)
    return {"agent_id": "agent_b", "feasible": list(private["feasible"]), "preferred": private["preferred"]}


def rule_plan_from_reports(task: dict[str, Any], reports: dict[str, dict[str, Any]], *, version: str) -> dict[str, Any]:
    privates = {}
    for agent_id, payload in reports.items():
        privates[agent_id] = {
            "feasible": list(payload.get("feasible") or []),
            "preferred": str(payload.get("preferred") or ""),
        }
    if "agent_a" not in privates or "agent_b" not in privates:
        assignments = {agent_id: str((payload or {}).get("preferred") or "") for agent_id, payload in reports.items()}
        return {"plan_version": version, "assignments": assignments, "rule": RULE_ID}
    return {
        "plan_version": version,
        "assignments": solve_from_privates(task, privates),
        "rule": RULE_ID,
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
    plan = oracle_plan(task, variant)
    return {"plan_version": PLAN_VERSION, "assignments": plan["assignments"], "rule": RULE_ID}


def report_prompt(task: dict[str, Any], agent_id: str, private: dict[str, Any]) -> str:
    return (
        _spec_block(task)
        + f"你是 {agent_id}。输出 {{\"agent_id\": \"{agent_id}\", \"feasible\": [...], \"preferred\": \"<slot>\"}}。\n"
        + "只能根据你自己的私有约束报告。不要编造对方约束。\n"
        + f"【你的私有约束】{json.dumps(private, ensure_ascii=False)}\n"
    )


def revision_prompt(task: dict[str, Any], private: dict[str, Any]) -> str:
    return (
        _spec_block(task)
        + "你是 agent_b。你收到一条私有约束修订。请提交最新可行集和首选。\n"
        + '输出 {"agent_id": "agent_b", "feasible": [...], "preferred": "<slot>"}。\n'
        + f"【修订后的私有约束】{json.dumps(private, ensure_ascii=False)}\n"
    )


def coordinator_initial_prompt(task: dict[str, Any], reports: dict[str, dict[str, Any]]) -> str:
    return (
        _spec_block(task)
        + "你是协调者。根据已送达的初始报告形成初始联合方案。不要执行占用。\n"
        + f'输出 {{"plan_version": "{INITIAL_VERSION}", "assignments": {{"agent_a": "<slot>", "agent_b": "<slot>"}}, "rule": "{RULE_ID}"}}。\n'
        + "只能使用已送达报告。不要编造未送达 Agent 的可行集。\n"
        + f"【已送达初始报告】{json.dumps(reports, ensure_ascii=False)}\n"
    )


def coordinator_propose_prompt(
    task: dict[str, Any],
    *,
    latest: dict[str, dict[str, Any]],
    initial_plan: dict[str, Any] | None,
    violations: list[dict[str, Any]],
) -> str:
    return (
        _spec_block(task)
        + "你是协调者。平台只返回违规证据，不会给出正确时段，也不会自动修正。\n"
        + "请调用 propose_joint_assignment：提交无重复占用的联合方案。Coordinator 不能替 A/B 执行。\n"
        + f'输出 {{"plan_version": "{PLAN_VERSION}", "assignments": {{"agent_a": "<slot>", "agent_b": "<slot>"}}, "rule": "{RULE_ID}"}}。\n'
        + "可选字段 initial_conflict_detected 仅作自我判断，不是世界事实。\n"
        + f"【初始方案】{json.dumps(initial_plan, ensure_ascii=False)}\n"
        + f"【违规证据】{json.dumps(violations, ensure_ascii=False)}\n"
        + f"【最新已送达约束】{json.dumps(latest, ensure_ascii=False)}\n"
    )


def commit_prompt(task: dict[str, Any], agent_id: str, private: dict[str, Any], plan: dict[str, Any] | None) -> str:
    return (
        _spec_block(task)
        + f"你是 {agent_id}。确认联合方案中分配给你的时段，并自己占用该时段。Coordinator 不能代你执行。\n"
        + f'输出 {{"agent_id": "{agent_id}", "plan_version": "{PLAN_VERSION}", "confirm": true或false, "slot": "<slot或null>"}}。\n'
        + "分配不在你的可行集内、方案缺失或版本不一致时 confirm=false。\n"
        + f"【你的私有约束】{json.dumps(private, ensure_ascii=False)}\n"
        + f"【联合方案】{json.dumps(plan, ensure_ascii=False)}\n"
    )


def direct_prompt(task: dict[str, Any], variant: str) -> str:
    def _view(private: dict[str, Any]) -> dict[str, Any]:
        return {
            "feasible": list(private["feasible"]),
            "preferred": private["preferred"],
            "priority": private["priority"],
            "window_token": private["window_token"],
        }

    both = {
        "agent_a": _view(agent_private(task, "agent_a", variant)),
        "agent_b": _view(agent_private(task, "agent_b", variant)),
    }
    return (
        _spec_block(task)
        + "你看到双方完整约束。直接给出唯一联合方案。这是可做性校准，不是正式多智能体结果。\n"
        + "assignments 中每个 Agent 的时段必须出现在该 Agent 的 feasible 列表里。\n"
        + f'输出 {{"plan_version": "{PLAN_VERSION}", "assignments": {{"agent_a": "<slot>", "agent_b": "<slot>"}}, "rule": "{RULE_ID}"}}。\n'
        + f"【双方私有约束】{json.dumps(both, ensure_ascii=False)}\n"
    )
