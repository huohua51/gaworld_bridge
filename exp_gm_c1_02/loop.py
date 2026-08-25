"""A/B + Coordinator. Drop revision drops B's latest constraint; Drop coordinator drops final plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_c1_02.budget import DIRECT_KINDS, BudgetMeter
from exp_gm_c1_02.channel import CoordinationChannel
from exp_gm_c1_02.contract import INITIAL_VERSION, PLAN_VERSION, commit_contract, parse_json_object, plan_contract, report_contract
from exp_gm_c1_02.loader import agent_baseline, agent_private, leak_tokens_for
from exp_gm_c1_02.prompts import (
    commit_prompt,
    coordinator_initial_prompt,
    coordinator_propose_prompt,
    direct_prompt,
    report_prompt,
    revision_prompt,
)
from gaworld.work.coordination import JointAssignmentChannel, occupancy_table

GenerateFn = Callable[[str], str]

ORACLE_MARKERS = (
    "c1_02_optics_table_001.json",
    "c1_02_greenhouse_001.json",
    "c1_02_cold_store_001.json",
    "hidden test",
    "test_oracle",
)


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def _oracle_in(*texts: str) -> list[str]:
    blob = "\n".join(texts)
    return [tok for tok in ORACLE_MARKERS if tok in blob]


def _feasible_map(latest: dict[str, dict[str, Any]], task: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "agent_a": list((latest.get("agent_a") or {}).get("feasible") or task["agent_a"]["feasible"]),
        "agent_b": list((latest.get("agent_b") or {}).get("feasible") or []),
    }


def run_direct(*, task: dict, variant: str, out_dir: Path, generate_fn: GenerateFn) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel = CoordinationChannel(out_dir / "coord.jsonl")
    budget = BudgetMeter(max_calls=1, expected=DIRECT_KINDS)
    private_a = agent_private(task, "agent_a", variant)
    private_b = agent_private(task, "agent_b", variant)
    channel.put_private("agent_a", private_a)
    channel.put_private("agent_b", private_b)
    prompt = direct_prompt(task, variant)
    raw = generate_fn(prompt) or ""
    parsed, error = plan_contract(parse_json_object(raw), version=PLAN_VERSION)
    budget.charge("direct_plan")
    world_path = out_dir / task["artifact"]
    if error == "ok":
        channel.emit_plan(parsed)
        channel.deliver_plan()
        for agent_id, slot in (parsed.get("assignments") or {}).items():
            channel.submit_claim(role=agent_id, agent_id=agent_id, slot=str(slot), plan_version=str(parsed.get("plan_version") or ""))
        channel.write_world(role="agent_a", path=world_path, content=json.dumps(channel.world_state(), ensure_ascii=False, indent=2))
    env = channel.write_world(role="environment", path=world_path, content="ENVIRONMENT_REWRITE")
    peek = channel.read_private("coordinator", "agent_a")
    (out_dir / "direct_prompt.txt").write_text(prompt, encoding="utf-8")
    (out_dir / "direct_raw.txt").write_text(raw, encoding="utf-8")
    return {
        "track": "direct",
        "variant": variant,
        "events": ["direct_plan"],
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "plan": parsed,
        "plan_error": error,
        "initial_plan": {},
        "initial_error": "ok",
        "reports": {"agent_a": {"agent_id": "agent_a", "feasible": private_a["feasible"], "preferred": private_a["preferred"]}, "agent_b": {"agent_id": "agent_b", "feasible": private_b["feasible"], "preferred": private_b["preferred"]}},
        "report_errors": {"agent_a": "ok", "agent_b": "ok"},
        "revision": {},
        "revision_error": "ok",
        "revision_delivered": True,
        "commits": {},
        "commit_errors": {},
        "world": channel.world_state(),
        "world_path": str(world_path) if world_path.is_file() else "",
        "violations": [],
        "ja_accepted": True,
        "unregistered_modification": 0,
        "a_ran": True,
        "b_ran": True,
        "coordinator_ran": True,
        "plan_delivered": True,
        "peek_denied": peek.get("reason") == "unauthorized_private_read",
        "env_denied": env.get("ok") is False,
        "leaks": _contains(prompt, leak_tokens_for(task, "intervention")) if variant != "intervention" else [],
        "oracle_in_prompt": _oracle_in(prompt),
        "prompts": {"direct": prompt},
    }


def run_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    out_dir: Path,
    report_a_fn: GenerateFn,
    report_b_fn: GenerateFn,
    initial_fn: GenerateFn,
    revision_fn: GenerateFn,
    propose_fn: GenerateFn,
    commit_a_fn: GenerateFn,
    commit_b_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel = CoordinationChannel(out_dir / "coord.jsonl")
    budget = BudgetMeter()
    events = ["task_started"]
    actual_a = agent_private(task, "agent_a", variant)
    actual_b = agent_private(task, "agent_b", variant)
    baseline_a = agent_baseline(task, "agent_a")
    baseline_b = agent_baseline(task, "agent_b")
    channel.put_private("agent_a", actual_a)
    channel.put_private("agent_b", actual_b)
    channel.read_private("agent_a", "agent_a")
    channel.read_private("agent_b", "agent_b")
    events.append("private_constraints_read")

    prompt_a = report_prompt(task, "agent_a", baseline_a)
    prompt_b = report_prompt(task, "agent_b", baseline_b)
    raw_a = report_a_fn(prompt_a) or ""
    report_a, err_a = report_contract(parse_json_object(raw_a), agent_id="agent_a")
    budget.charge("agent_a_report")
    if err_a == "ok":
        channel.emit_report("agent_a", report_a)
        channel.deliver_report("agent_a")
        events.append("agent_a_reported")
    raw_b = report_b_fn(prompt_b) or ""
    report_b, err_b = report_contract(parse_json_object(raw_b), agent_id="agent_b")
    budget.charge("agent_b_report")
    if err_b == "ok":
        channel.emit_report("agent_b", report_b)
        channel.deliver_report("agent_b")
        events.append("agent_b_reported")

    baseline_inbox = channel.read_reports("coordinator").get("reports") or {}
    events.append("coordinator_collected_initial")
    initial_p = coordinator_initial_prompt(task, baseline_inbox)
    raw_init = initial_fn(initial_p) or ""
    initial_plan, initial_err = plan_contract(parse_json_object(raw_init), version=INITIAL_VERSION)
    budget.charge("coordinator_initial")
    events.append("joint_plan_initial")

    rev_private = actual_b
    rev_p = revision_prompt(task, rev_private)
    raw_rev = revision_fn(rev_p) or ""
    revision, rev_err = report_contract(parse_json_object(raw_rev), agent_id="agent_b")
    budget.charge("agent_b_revision")
    revision_delivered = False
    if rev_err == "ok":
        channel.emit_revision("agent_b", revision)
        delivered = channel.deliver_revision("agent_b", drop=track == "drop_revision")
        revision_delivered = bool(delivered.get("ok")) and not delivered.get("dropped")
        events.append("agent_b_revision_dropped" if track == "drop_revision" else "agent_b_revision_sent")

    latest = channel.latest_delivered_constraints()
    naive = {
        "agent_a": str((latest.get("agent_a") or {}).get("preferred") or ""),
        "agent_b": str((latest.get("agent_b") or {}).get("preferred") or ""),
    }
    ja = JointAssignmentChannel(
        resource_id=str(task["resource_id"]),
        slots=list(task["slots"]),
        priority=list(task["priority"]),
        feasible=_feasible_map(latest, task),
        max_retries=0,
        path=out_dir / "ja.jsonl",
    )
    if naive["agent_a"] and naive["agent_b"]:
        ja.save_initial(naive)
    inspect = ja.inspect_violations() if naive["agent_a"] and naive["agent_b"] else {"ok": True, "violations": []}
    violations = list(inspect.get("violations") or [])
    events.append("channel_inspected")

    propose_p = coordinator_propose_prompt(task, latest=latest, initial_plan=initial_plan or None, violations=violations)
    raw_plan = propose_fn(propose_p) or ""
    plan, plan_err = plan_contract(parse_json_object(raw_plan), version=PLAN_VERSION)
    budget.charge("coordinator_propose")
    events.append("joint_plan_proposed")
    ja_accepted = False
    if plan_err == "ok":
        proposed = ja.propose_joint_assignment("coordinator", plan["assignments"])
        ja_accepted = bool(proposed.get("accepted"))
        channel.emit_plan(plan)
        delivered_plan = channel.deliver_plan(drop=track == "drop_coordinator")
        if delivered_plan.get("dropped"):
            events.append("joint_plan_dropped")
        else:
            events.append("joint_plan_delivered")

    plan_for_a = channel.read_plan("agent_a")
    plan_for_b = channel.read_plan("agent_b")
    commit_p_a = commit_prompt(task, "agent_a", actual_a, plan_for_a.get("plan") if plan_for_a.get("ok") else None)
    commit_p_b = commit_prompt(task, "agent_b", actual_b, plan_for_b.get("plan") if plan_for_b.get("ok") else None)
    raw_ca = commit_a_fn(commit_p_a) or ""
    commit_a, err_ca = commit_contract(parse_json_object(raw_ca), agent_id="agent_a")
    budget.charge("agent_a_commit")
    raw_cb = commit_b_fn(commit_p_b) or ""
    commit_b, err_cb = commit_contract(parse_json_object(raw_cb), agent_id="agent_b")
    budget.charge("agent_b_commit")
    if err_ca == "ok" and commit_a.get("confirm") and commit_a.get("slot"):
        channel.submit_claim(role="agent_a", agent_id="agent_a", slot=str(commit_a["slot"]), plan_version=str(commit_a["plan_version"]))
        events.append("agent_a_executed")
    if err_cb == "ok" and commit_b.get("confirm") and commit_b.get("slot"):
        channel.submit_claim(role="agent_b", agent_id="agent_b", slot=str(commit_b["slot"]), plan_version=str(commit_b["plan_version"]))
        events.append("agent_b_executed")
    world_path = out_dir / task["artifact"]
    channel.write_world(role="agent_a", path=world_path, content=json.dumps(channel.world_state(), ensure_ascii=False, indent=2))
    env = channel.write_world(role="environment", path=world_path, content="ENVIRONMENT_REWRITE")
    coord_exec = channel.submit_claim(role="coordinator", agent_id="agent_a", slot="stolen", plan_version=PLAN_VERSION)
    peek_coord_a = channel.read_private("coordinator", "agent_a")
    peek_a_b = channel.read_private("agent_a", "agent_b")
    prompts = {
        "agent_a_report": prompt_a,
        "agent_b_report": prompt_b,
        "coordinator_initial": initial_p,
        "agent_b_revision": rev_p,
        "coordinator_propose": propose_p,
        "agent_a_commit": commit_p_a,
        "agent_b_commit": commit_p_b,
    }
    for name, text in prompts.items():
        (out_dir / f"{name}.txt").write_text(text, encoding="utf-8")
    (out_dir / "raw.json").write_text(
        json.dumps(
            {"report_a": raw_a, "report_b": raw_b, "initial": raw_init, "revision": raw_rev, "plan": raw_plan, "commit_a": raw_ca, "commit_b": raw_cb},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "inspect.json").write_text(json.dumps(inspect, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    leak_tokens = leak_tokens_for(task, "intervention")
    leaks = []
    leaks.extend(_contains(prompt_a, leak_tokens))
    leaks.extend(_contains(commit_p_a, leak_tokens))
    if track == "drop_revision":
        leaks.extend(_contains(propose_p, leak_tokens))
        leaks.extend(_contains(initial_p, leak_tokens))
    return {
        "track": track,
        "variant": variant,
        "events": events,
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "reports": {"agent_a": report_a, "agent_b": report_b},
        "report_errors": {"agent_a": err_a, "agent_b": err_b},
        "revision": revision,
        "revision_error": rev_err,
        "revision_delivered": revision_delivered,
        "initial_plan": initial_plan,
        "initial_error": initial_err,
        "plan": plan,
        "plan_error": plan_err,
        "commits": {"agent_a": commit_a, "agent_b": commit_b},
        "commit_errors": {"agent_a": err_ca, "agent_b": err_cb},
        "world": channel.world_state(),
        "world_path": str(world_path) if world_path.is_file() else "",
        "violations": violations,
        "ja_accepted": ja_accepted,
        "unregistered_modification": ja.unregistered_modification,
        "occupancy": occupancy_table(channel.world_state().get("by_agent") or {}),
        "a_ran": True,
        "b_ran": True,
        "coordinator_ran": True,
        "plan_delivered": track != "drop_coordinator" and plan_err == "ok",
        "drop_revision_isolated": track != "drop_revision" or (not revision_delivered and "agent_b" in baseline_inbox),
        "drop_coordinator_isolated": track != "drop_coordinator" or channel.plan_dropped,
        "peek_denied": peek_coord_a.get("reason") == "unauthorized_private_read" and peek_a_b.get("reason") == "unauthorized_private_read",
        "env_denied": env.get("ok") is False,
        "coordinator_exec_denied": coord_exec.get("ok") is False,
        "leaks": leaks,
        "oracle_in_prompt": _oracle_in(*prompts.values()),
        "prompts": prompts,
        "latest": latest,
        "naive": naive,
    }
