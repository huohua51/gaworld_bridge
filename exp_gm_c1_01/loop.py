"""Two executors + coordinator. Drop discards agent_b's constraint report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_c1_01.budget import DIRECT_KINDS, BudgetMeter
from exp_gm_c1_01.channel import CoordinationChannel
from exp_gm_c1_01.contract import commit_contract, parse_json_object, plan_contract, report_contract
from exp_gm_c1_01.loader import agent_private, leak_tokens_for
from exp_gm_c1_01.prompts import commit_prompt, coordinator_prompt, direct_prompt, report_prompt

GenerateFn = Callable[[str], str]

ORACLE_MARKERS = (
    "c1_charge_slot_001.json",
    "c1_device_book_001.json",
    "c1_dock_window_001.json",
    "hidden test",
    "test_oracle",
)


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def _oracle_in(*texts: str) -> list[str]:
    blob = "\n".join(texts)
    return [tok for tok in ORACLE_MARKERS if tok in blob]


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
    parsed, error = plan_contract(parse_json_object(raw))
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
        "prompt": prompt,
        "plan": parsed,
        "plan_error": error,
        "reports": {"agent_a": {"agent_id": "agent_a", "feasible": private_a["feasible"], "preferred": private_a["preferred"]}, "agent_b": {"agent_id": "agent_b", "feasible": private_b["feasible"], "preferred": private_b["preferred"]}},
        "report_errors": {"agent_a": "ok", "agent_b": "ok"},
        "commits": {},
        "commit_errors": {},
        "world": channel.world_state(),
        "world_path": str(world_path) if world_path.is_file() else "",
        "channel": channel,
        "a_ran": True,
        "b_ran": True,
        "coordinator_ran": True,
        "b_delivered": True,
        "drop_inbox_missing_b": False,
        "peek_denied": peek.get("reason") == "unauthorized_private_read",
        "env_denied": env.get("ok") is False,
        "leaks": _contains(prompt, leak_tokens_for(task, "intervention")) if variant != "intervention" else [],
        "oracle_in_prompt": _oracle_in(prompt),
        "prompts": {"direct": prompt},
        "report_trace": {},
    }


def run_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    out_dir: Path,
    report_a_fn: GenerateFn,
    report_b_fn: GenerateFn,
    plan_fn: GenerateFn,
    commit_a_fn: GenerateFn,
    commit_b_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel = CoordinationChannel(out_dir / "coord.jsonl")
    budget = BudgetMeter()
    events = ["task_started"]
    private_a = agent_private(task, "agent_a", variant)
    private_b = agent_private(task, "agent_b", variant)
    channel.put_private("agent_a", private_a)
    channel.put_private("agent_b", private_b)
    got_a = channel.read_private("agent_a", "agent_a")
    got_b = channel.read_private("agent_b", "agent_b")
    events.append("private_constraints_read")
    global_view = track == "single"
    peer_for_a = private_b if global_view else None
    peer_for_b = private_a if global_view else None
    prompt_a = report_prompt(task, "agent_a", got_a.get("payload") or private_a, peer_private=peer_for_a)
    prompt_b = report_prompt(task, "agent_b", got_b.get("payload") or private_b, peer_private=peer_for_b)
    raw_a = report_a_fn(prompt_a) or ""
    report_a, err_a = report_contract(parse_json_object(raw_a), agent_id="agent_a")
    budget.charge("agent_a_report")
    if err_a == "ok":
        channel.emit_report("agent_a", report_a)
        channel.deliver_report("agent_a", drop=False)
        events.append("agent_a_reported")
    raw_b = report_b_fn(prompt_b) or ""
    report_b, err_b = report_contract(parse_json_object(raw_b), agent_id="agent_b")
    budget.charge("agent_b_report")
    b_delivered = False
    if err_b == "ok":
        channel.emit_report("agent_b", report_b)
        delivered = channel.deliver_report("agent_b", drop=track == "drop")
        b_delivered = bool(delivered.get("ok")) and not delivered.get("dropped")
        events.append("agent_b_dropped" if track == "drop" else "agent_b_reported")
    inbox = channel.read_reports("coordinator")
    reports = inbox.get("reports") or {}
    events.append("coordinator_collected")
    both_private = {"agent_a": private_a, "agent_b": private_b} if global_view else None
    plan_p = coordinator_prompt(task, reports, global_view=global_view, both_private=both_private)
    raw_plan = plan_fn(plan_p) or ""
    plan, plan_err = plan_contract(parse_json_object(raw_plan))
    budget.charge("coordinator_plan")
    events.append("joint_plan_emitted")
    if plan_err == "ok":
        channel.emit_plan(plan)
        channel.deliver_plan()
        events.append("joint_plan_delivered")
    plan_for_a = channel.read_plan("agent_a")
    plan_for_b = channel.read_plan("agent_b")
    commit_p_a = commit_prompt(task, "agent_a", private_a, plan_for_a.get("plan") if plan_for_a.get("ok") else None)
    commit_p_b = commit_prompt(task, "agent_b", private_b, plan_for_b.get("plan") if plan_for_b.get("ok") else None)
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
    peek_coord_a = channel.read_private("coordinator", "agent_a")
    peek_a_b = channel.read_private("agent_a", "agent_b")
    prompts = {
        "agent_a_report": prompt_a,
        "agent_b_report": prompt_b,
        "coordinator_plan": plan_p,
        "agent_a_commit": commit_p_a,
        "agent_b_commit": commit_p_b,
    }
    for name, text in prompts.items():
        (out_dir / f"{name}.txt").write_text(text, encoding="utf-8")
    (out_dir / "raw.json").write_text(
        json.dumps(
            {"report_a": raw_a, "report_b": raw_b, "plan": raw_plan, "commit_a": raw_ca, "commit_b": raw_cb},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    leak_tokens = leak_tokens_for(task, "intervention")
    leaks = []
    if track != "single":
        leaks.extend(_contains(prompt_a, leak_tokens))
        leaks.extend(_contains(commit_p_a, leak_tokens))
        if track == "drop":
            leaks.extend(_contains(plan_p, leak_tokens))
    return {
        "track": track,
        "variant": variant,
        "events": events,
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "reports": {"agent_a": report_a, "agent_b": report_b},
        "report_errors": {"agent_a": err_a, "agent_b": err_b},
        "delivered_reports": reports,
        "plan": plan,
        "plan_error": plan_err,
        "commits": {"agent_a": commit_a, "agent_b": commit_b},
        "commit_errors": {"agent_a": err_ca, "agent_b": err_cb},
        "world": channel.world_state(),
        "world_path": str(world_path) if world_path.is_file() else "",
        "channel": channel,
        "a_ran": True,
        "b_ran": True,
        "coordinator_ran": True,
        "b_delivered": b_delivered,
        "drop_inbox_missing_b": track != "drop" or ("agent_b" not in reports),
        "peek_denied": peek_coord_a.get("reason") == "unauthorized_private_read" and peek_a_b.get("reason") == "unauthorized_private_read",
        "env_denied": env.get("ok") is False,
        "leaks": leaks,
        "oracle_in_prompt": _oracle_in(*prompts.values()),
        "prompts": prompts,
        "report_trace": channel.report_trace(),
        "hashes_ok_a": channel.hashes_match("agent_a"),
        "hashes_ok_b": channel.hashes_match("agent_b") if track != "drop" else channel.hashes_match("agent_b"),
    }
