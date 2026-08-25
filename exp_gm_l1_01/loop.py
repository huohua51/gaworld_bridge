"""Worker A starts; optional interrupt; Coordinator hands off; successor continues."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from exp_gm_l1_01.budget import DIRECT_KINDS, BudgetMeter
from exp_gm_l1_01.contract import (
    checkpoint_contract,
    direct_contract,
    handoff_contract,
    parse_json_object,
    resume_contract,
    step_contract,
)
from exp_gm_l1_01.loader import leak_tokens_for, solve_outputs, worker_private
from exp_gm_l1_01.prompts import (
    checkpoint_prompt,
    coordinator_prompt,
    direct_prompt,
    resume_prompt,
    step1_prompt,
    successor_step_prompt,
)
from gaworld.work.continuity import WorkflowCheckpointChannel

GenerateFn = Callable[[str], str]
ORACLE_MARKERS = (
    "l1_01_inventory_lots_001.json",
    "l1_01_centrifuge_rotor_001.json",
    "l1_01_specimen_log_001.json",
    "hidden test",
    "test_oracle",
)


def _contains(text: str, tokens: list[str]) -> list[str]:
    return [tok for tok in tokens if tok and tok in (text or "")]


def _oracle_in(*texts: str) -> list[str]:
    blob = "\n".join(texts)
    return [tok for tok in ORACLE_MARKERS if tok in blob]


def _payload(result: dict[str, Any], key: str) -> dict[str, Any] | None:
    if not result.get("ok"):
        return None
    return result.get(key)


def run_direct(*, task: dict, variant: str, out_dir: Path, generate_fn: GenerateFn) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel = WorkflowCheckpointChannel(step_ids=list(task["step_ids"]), path=out_dir / "continuity.jsonl")
    budget = BudgetMeter(max_calls=1, expected=DIRECT_KINDS)
    private_a = worker_private(task, "worker_a")
    channel.put_private("worker_a", private_a)
    prompt = direct_prompt(task, variant)
    raw = generate_fn(prompt) or ""
    required = list(task["step_ids"] if variant == "control" else task["step_ids"][1:])
    parsed, error = direct_contract(parse_json_object(raw), required_ids=required)
    budget.charge("direct_plan")
    if variant == "intervention":
        first = task["step_ids"][0]
        channel.execute_step(role="worker_a", step_id=first, output=dict(solve_outputs(task)[first]))
    if error == "ok":
        completed = set(channel.world_state().get("completed_steps") or [])
        for step_id in task["step_ids"]:
            if step_id in completed or step_id not in parsed["steps"]:
                continue
            channel.execute_step(role="worker_a", step_id=step_id, output=dict(parsed["steps"][step_id]))
    world_path = out_dir / task["artifact"]
    channel.write_world(role="worker_a", path=world_path, content=json.dumps(channel.world_state(), ensure_ascii=False, indent=2))
    env = channel.write_world(role="environment", path=world_path, content="ENVIRONMENT_REWRITE")
    peek = channel.read_private("coordinator", "worker_a")
    (out_dir / "direct_prompt.txt").write_text(prompt, encoding="utf-8")
    (out_dir / "direct_raw.txt").write_text(raw, encoding="utf-8")
    return {
        "track": "direct",
        "variant": variant,
        "events": ["direct_plan"],
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "direct": parsed,
        "direct_error": error,
        "world": channel.world_state(),
        "world_path": str(world_path) if world_path.is_file() else "",
        "checkpoint_created": False,
        "checkpoint_delivered_b": False,
        "handoff_completed": False,
        "resume_step": "",
        "resume_declared": "",
        "duplicates": [],
        "a_ran": True,
        "b_ran": variant == "intervention",
        "coordinator_ran": True,
        "peek_denied": peek.get("reason") == "unauthorized_private_read",
        "env_denied": env.get("ok") is False,
        "coordinator_exec_denied": True,
        "leaks": _contains(prompt, leak_tokens_for(task, "intervention")) if variant != "intervention" else [],
        "oracle_in_prompt": _oracle_in(prompt),
        "prompts": {"direct": prompt},
        "recovery_latency": None,
        "drop_checkpoint_isolated": True,
        "drop_handoff_isolated": True,
    }


def run_cell(
    *,
    task: dict,
    variant: str,
    track: str,
    out_dir: Path,
    step1_fn: GenerateFn,
    checkpoint_fn: GenerateFn,
    handoff_fn: GenerateFn,
    resume_fn: GenerateFn,
    step2_fn: GenerateFn,
    step3_fn: GenerateFn,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    channel = WorkflowCheckpointChannel(step_ids=list(task["step_ids"]), path=out_dir / "continuity.jsonl")
    budget = BudgetMeter()
    events = ["task_started"]
    private_a = worker_private(task, "worker_a")
    private_b = worker_private(task, "worker_b")
    channel.put_private("worker_a", private_a)
    channel.put_private("worker_b", private_b)
    channel.read_private("worker_a", "worker_a")
    channel.read_private("worker_b", "worker_b")

    prompt_s1 = step1_prompt(task, private_a)
    raw_s1 = step1_fn(prompt_s1) or ""
    step1, err_s1 = step_contract(parse_json_object(raw_s1), worker_id="worker_a")
    budget.charge("worker_a_step1")
    if err_s1 == "ok":
        executed = channel.execute_step(role="worker_a", step_id=str(step1["step_id"]), output=dict(step1["output"]))
        if executed.get("ok"):
            events.append("worker_a_step1")

    world_now = channel.world_state()
    prompt_ck = checkpoint_prompt(task, list(world_now["completed_steps"]), {sid: world_now["steps"][sid]["output"] for sid in world_now["completed_steps"]})
    raw_ck = checkpoint_fn(prompt_ck) or ""
    ckpt_req, err_ck = checkpoint_contract(parse_json_object(raw_ck), worker_id="worker_a")
    budget.charge("worker_a_checkpoint")
    emitted = {"ok": False}
    if err_ck == "ok":
        emitted = channel.emit_checkpoint(role="worker_a", completed_steps=list(ckpt_req["completed_steps"]), outputs=dict(ckpt_req["outputs"]))
        if emitted.get("ok"):
            events.append("checkpoint_created")
    channel.deliver_checkpoint("coordinator", drop=False)
    channel.deliver_checkpoint("worker_a", drop=False)
    dropped_ckpt = track == "drop_checkpoint"
    channel.deliver_checkpoint("worker_b", drop=dropped_ckpt)
    if dropped_ckpt:
        events.append("checkpoint_dropped")
    else:
        events.append("checkpoint_delivered")

    if variant == "intervention":
        channel.mark_unavailable("worker_a")
        events.append("worker_a_unavailable")

    ck_for_coord = _payload(channel.read_checkpoint("coordinator"), "checkpoint")
    prompt_h = coordinator_prompt(task, variant, ck_for_coord, a_unavailable=variant == "intervention")
    raw_h = handoff_fn(prompt_h) or ""
    handoff, err_h = handoff_contract(parse_json_object(raw_h))
    budget.charge("coordinator_handoff")
    if err_h == "ok":
        channel.emit_handoff(
            role="coordinator",
            successor=str(handoff["successor"]),
            checkpoint_version=str(handoff["checkpoint_version"]),
            resume_step=str(handoff["resume_step"]),
        )
        events.append("handoff_emitted")
    channel.deliver_handoff("worker_a", drop=False)
    dropped_h = track == "drop_handoff"
    channel.deliver_handoff("worker_b", drop=dropped_h)
    if dropped_h:
        events.append("handoff_dropped")
    else:
        events.append("handoff_delivered")

    successor = "worker_b" if variant == "intervention" else "worker_a"
    private_s = private_b if successor == "worker_b" else private_a
    ck_read = channel.read_checkpoint(successor)
    ho_read = channel.read_handoff(successor)
    ck_body = _payload(ck_read, "checkpoint")
    ho_body = _payload(ho_read, "handoff")
    prompt_r = resume_prompt(task, successor, ck_body, ho_body)
    raw_r = resume_fn(prompt_r) or ""
    resume, err_r = resume_contract(parse_json_object(raw_r), worker_id=successor)
    budget.charge("successor_resume")
    events.append("successor_resume")

    session_outputs = dict((ck_body or {}).get("outputs") or {})
    step_ids = list(task["step_ids"])
    step2_id, step3_id = step_ids[1], step_ids[2]
    prompt_s2 = successor_step_prompt(task, successor, step2_id, private_s, ck_body, session_outputs)
    raw_s2 = step2_fn(prompt_s2) or ""
    step2, err_s2 = step_contract(parse_json_object(raw_s2), worker_id=successor)
    budget.charge("successor_step2")
    if err_s2 == "ok":
        executed = channel.execute_step(role=successor, step_id=str(step2["step_id"]), output=dict(step2["output"]))
        if executed.get("ok"):
            session_outputs[str(step2["step_id"])] = dict(step2["output"])
            events.append("successor_step2")
        elif executed.get("reason") == "duplicate_action":
            events.append("duplicate_action")
        elif executed.get("reason") == "resume_from_wrong_step":
            events.append("resume_from_wrong_step")
    elif err_s2 == "idle":
        events.append("successor_idle_step2")

    prompt_s3 = successor_step_prompt(task, successor, step3_id, private_s, ck_body, session_outputs)
    raw_s3 = step3_fn(prompt_s3) or ""
    step3, err_s3 = step_contract(parse_json_object(raw_s3), worker_id=successor)
    budget.charge("successor_step3")
    if err_s3 == "ok":
        executed = channel.execute_step(role=successor, step_id=str(step3["step_id"]), output=dict(step3["output"]))
        if executed.get("ok"):
            session_outputs[str(step3["step_id"])] = dict(step3["output"])
            events.append("successor_step3")
        elif executed.get("reason") == "duplicate_action":
            events.append("duplicate_action")
        elif executed.get("reason") == "resume_from_wrong_step":
            events.append("resume_from_wrong_step")
    elif err_s3 == "idle":
        events.append("successor_idle_step3")

    world_path = out_dir / task["artifact"]
    channel.write_world(role="worker_a" if variant == "control" else successor, path=world_path, content=json.dumps(channel.world_state(), ensure_ascii=False, indent=2))
    env = channel.write_world(role="environment", path=world_path, content="ENVIRONMENT_REWRITE")
    coord_exec = channel.execute_step(role="coordinator", step_id=step_ids[1], output={"stolen": True})
    peek_coord = channel.read_private("coordinator", "worker_a")
    peek_b_a = channel.read_private("worker_b", "worker_a")
    prompts = {
        "worker_a_step1": prompt_s1,
        "worker_a_checkpoint": prompt_ck,
        "coordinator_handoff": prompt_h,
        "successor_resume": prompt_r,
        "successor_step2": prompt_s2,
        "successor_step3": prompt_s3,
    }
    for name, text in prompts.items():
        (out_dir / f"{name}.txt").write_text(text, encoding="utf-8")
    (out_dir / "raw.json").write_text(
        json.dumps(
            {
                "step1": raw_s1,
                "checkpoint": raw_ck,
                "handoff": raw_h,
                "resume": raw_r,
                "step2": raw_s2,
                "step3": raw_s3,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    leak_tokens = leak_tokens_for(task, "intervention")
    leaks = []
    if variant != "intervention":
        for text in prompts.values():
            leaks.extend(_contains(text, leak_tokens_for(task, "intervention") or [task["interrupt_token"]]))
    else:
        leaks.extend(_contains(prompt_s1, leak_tokens))
        leaks.extend(_contains(prompt_ck, leak_tokens))
        if track == "drop_handoff":
            leaks.extend(_contains(prompt_r, leak_tokens))
    world = channel.world_state()
    resume_declared = "" if err_r != "ok" else str(resume.get("resume_step") or "")
    return {
        "track": track,
        "variant": variant,
        "events": events,
        "budget": budget.to_dict(),
        "budget_valid": budget.valid,
        "step1": step1,
        "step1_error": err_s1,
        "checkpoint_req": ckpt_req,
        "checkpoint_error": err_ck,
        "handoff": handoff,
        "handoff_error": err_h,
        "resume": resume,
        "resume_error": err_r,
        "step2": step2,
        "step2_error": err_s2,
        "step3": step3,
        "step3_error": err_s3,
        "world": world,
        "world_path": str(world_path) if world_path.is_file() else "",
        "checkpoint_created": channel.checkpoint_created(),
        "checkpoint_delivered_b": "worker_b" not in channel.checkpoint_dropped_for and bool(ck_body if successor == "worker_b" else True),
        "checkpoint_delivered_successor": ck_body is not None,
        "handoff_completed": ho_body is not None and err_h == "ok",
        "resume_step_expected": task["step_ids"][1],
        "resume_declared": resume_declared,
        "duplicates": list(world.get("duplicates") or []),
        "a_ran": True,
        "b_ran": successor == "worker_b",
        "coordinator_ran": True,
        "successor": successor,
        "peek_denied": peek_coord.get("reason") == "unauthorized_private_read" and peek_b_a.get("reason") == "unauthorized_private_read",
        "env_denied": env.get("ok") is False,
        "coordinator_exec_denied": coord_exec.get("ok") is False,
        "leaks": leaks,
        "oracle_in_prompt": _oracle_in(*prompts.values()),
        "prompts": prompts,
        "recovery_latency": channel.recovery_latency(),
        "drop_checkpoint_isolated": track != "drop_checkpoint" or bool(channel.checkpoint_dropped_for),
        "drop_handoff_isolated": track != "drop_handoff" or bool(channel.handoff_dropped_for),
        "completed_work_preserved": channel.completed_work_preserved(),
        "checkpoint_version_used": str((resume or {}).get("checkpoint_version") or (ck_body or {}).get("checkpoint_version") or ""),
    }
