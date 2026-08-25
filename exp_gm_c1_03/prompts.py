"""C1-03 prompts. Protection token only after revision delivery. Oracle never enters prompts."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_c1_03.contract import INITIAL_VERSION, PLAN_VERSION, RULE_ID
from exp_gm_c1_03.loader import agent_private, oracle_plan, protection_spec, public_spec, solve_final, solve_phase1


def _spec_block(task: dict[str, Any], variant: str, *, after_protection: bool = False) -> str:
    spec = public_spec(task, variant, after_protection=after_protection)
    return (
        f"【共同资源】{spec['resource_id']} 同一时段只能被一个 Agent 占用。\n"
        f"【可选时段】{json.dumps(spec['slots'], ensure_ascii=False)}\n"
        f"【优先级】{' > '.join(spec['priority'])}\n"
        f"【解决规则】{spec['rule_text']}\n"
        "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
    )


def _privates_from_reports(reports: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for agent_id, payload in reports.items():
        out[agent_id] = {
            "feasible": list(payload.get("feasible") or []),
            "preferred": str(payload.get("preferred") or ""),
        }
    return out


def rule_report(task: dict[str, Any], agent_id: str, variant: str) -> dict[str, Any]:
    private = agent_private(task, agent_id, variant)
    return {"agent_id": agent_id, "feasible": list(private["feasible"]), "preferred": private["preferred"]}


def rule_plan_from_reports(task: dict[str, Any], reports: dict[str, dict[str, Any]], *, version: str, variant: str, stage: str) -> dict[str, Any]:
    privates = _privates_from_reports(reports)
    if "agent_a" not in privates or "agent_b" not in privates:
        assignments = {agent_id: str((payload or {}).get("preferred") or "") for agent_id, payload in reports.items()}
        return {"plan_version": version, "assignments": assignments, "rule": RULE_ID}
    if stage == "phase1":
        assignments = solve_phase1(task, variant, privates)
    else:
        assignments = solve_final(task, variant, privates)
    return {"plan_version": version, "assignments": assignments, "rule": RULE_ID}


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


def report_prompt(task: dict[str, Any], agent_id: str, private: dict[str, Any], variant: str) -> str:
    return (
        _spec_block(task, variant)
        + f"你是 {agent_id}。输出 {{\"agent_id\": \"{agent_id}\", \"feasible\": [...], \"preferred\": \"<slot>\"}}。\n"
        + "只能根据你自己的私有约束报告。不要编造对方约束。\n"
        + f"【你的私有约束】{json.dumps(private, ensure_ascii=False)}\n"
    )


def coordinator_initial_prompt(task: dict[str, Any], reports: dict[str, dict[str, Any]], variant: str) -> str:
    return (
        _spec_block(task, variant)
        + "你是协调者。根据已送达的初始报告形成第一版联合方案。不要执行占用。\n"
        + f'输出 {{"plan_version": "{INITIAL_VERSION}", "assignments": {{"agent_a": "<slot>", "agent_b": "<slot>"}}, "rule": "{RULE_ID}"}}。\n'
        + "只能使用已送达报告。不要编造未送达 Agent 的可行集。\n"
        + f"【已送达初始报告】{json.dumps(reports, ensure_ascii=False)}\n"
    )


def coordinator_retry_prompt(
    task: dict[str, Any],
    variant: str,
    *,
    reports: dict[str, dict[str, Any]],
    first_plan: dict[str, Any] | None,
    violations: list[dict[str, Any]],
    protection_delivered: bool,
) -> str:
    protected = protection_spec(task)
    a = reports.get("agent_a") or {}
    b = reports.get("agent_b") or {}
    if protection_delivered:
        body = (
            _spec_block(task, variant, after_protection=True)
            + "你是协调者。登记过的优先级或保护状态已发生修订。平台只返回违规证据，不会给出低优先级的正确时段，也不会自动修正。\n"
            + "请调用 propose_joint_assignment：提交无重复占用的联合方案。Coordinator 不能替 A/B 执行。\n"
            + f'输出 {{"plan_version": "{PLAN_VERSION}", "assignments": {{"agent_a": "<slot>", "agent_b": "<slot>"}}, "rule": "{RULE_ID}"}}。\n'
        )
        if violations:
            body += "【重试】平台拒绝了上一份方案。必须根据新 NACK 重新提交，不要把被拒绝方案原样交回。\n"
            body += "不要为了消除冲突而改动被保护的高优先级原分配。不要把两个 Agent 分到同一时段。\n"
        else:
            body += "当前第一版方案仍满足修订后的保护约束。请提交最终 plan-001。\n"
        body += f"【登记保护修订】高优先级已修订为 {protected['agent']}。必须保持其最初申报的首选。令牌：{protected['token']}\n"
        body += f"【被保护的高优先级原分配】{json.dumps({'agent': 'A', 'must_keep': protected['slot']}, ensure_ascii=False)}\n"
        body += f"【违规证据】{json.dumps(violations, ensure_ascii=False)}\n"
        body += f"【被拒绝的方案】{json.dumps((first_plan or {}).get('assignments') or first_plan, ensure_ascii=False)}\n"
        body += f"【Agent A 可行集】{json.dumps(a.get('feasible') or [], ensure_ascii=False)}，首选 {a.get('preferred')}\n"
        body += f"【Agent B 可行集】{json.dumps(b.get('feasible') or [], ensure_ascii=False)}，首选 {b.get('preferred')}\n"
        body += f"【已送达初始报告】{json.dumps(reports, ensure_ascii=False)}\n"
        return body
    return (
        _spec_block(task, variant)
        + "你是协调者。请提交最终联合方案。不要执行占用。\n"
        + f'输出 {{"plan_version": "{PLAN_VERSION}", "assignments": {{"agent_a": "<slot>", "agent_b": "<slot>"}}, "rule": "{RULE_ID}"}}。\n'
        + "只能使用已送达报告。没有新的保护修订送达。\n"
        + f"【第一版方案】{json.dumps(first_plan, ensure_ascii=False)}\n"
        + f"【已送达初始报告】{json.dumps(reports, ensure_ascii=False)}\n"
    )


def commit_prompt(
    task: dict[str, Any],
    agent_id: str,
    private: dict[str, Any],
    plan: dict[str, Any] | None,
    variant: str,
    *,
    after_protection: bool,
) -> str:
    return (
        _spec_block(task, variant, after_protection=after_protection)
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
    protected = protection_spec(task)
    final = {
        "agent_a": {
            **both["agent_a"],
            "preferred": str(protected["slot"]),
            "priority": "high",
        },
        "agent_b": {
            **both["agent_b"],
            "priority": "low",
        },
    }
    body = (
        _spec_block(task, variant, after_protection=True)
        + "你看到完整时间线。直接给出最终唯一联合方案。这是可做性校准，不是正式多智能体结果。\n"
        + "assignments 中每个 Agent 的时段必须出现在该 Agent 的 feasible 列表里。\n"
        + f'输出 {{"plan_version": "{PLAN_VERSION}", "assignments": {{"agent_a": "<slot>", "agent_b": "<slot>"}}, "rule": "{RULE_ID}"}}。\n'
        + f"【第一阶段双方私有约束】{json.dumps(both, ensure_ascii=False)}\n"
        + f"【第一阶段优先级】{' > '.join(public_spec(task, variant)['priority'])}\n"
    )
    if variant == "intervention":
        body += (
            "【随后发生的登记保护修订】高优先级修订为 agent_a。"
            f"必须保持档案保护时段 {protected['slot']}，不要沿用第一阶段申报首选。"
            f"令牌：{protected['token']}\n"
        )
    else:
        body += "【随后的保护登记】与第一阶段一致，高优先级仍为 agent_a。\n"
    body += f"【最终约束】{json.dumps(final, ensure_ascii=False)}\n"
    return body
