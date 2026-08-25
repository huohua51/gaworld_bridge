"""L1-01 prompts. Interrupt token only after A is unavailable. Oracle files never enter prompts."""

from __future__ import annotations

import json
from typing import Any

from exp_gm_l1_01b.contract import CHECKPOINT_VERSION
from exp_gm_l1_01b.loader import public_spec, resume_step_for, solve_outputs, solve_step, worker_private
from gaworld.work.continuity import next_step


def _spec_block(task: dict[str, Any]) -> str:
    spec = public_spec(task)
    return (
        f"【任务】{spec['title']}\n"
        f"【步骤】{json.dumps(spec['steps'], ensure_ascii=False)}\n"
        f"【规则】{spec['rule_text']}\n"
        f"【输出字段】{spec['output_rule']}\n"
        "只输出一个 JSON 对象。不要输出解释、Markdown 或其它文字。\n"
    )


def rule_step(task: dict[str, Any], worker_id: str, step_id: str, prior: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"worker_id": worker_id, "step_id": step_id, "output": solve_step(task, step_id, prior)}


def rule_checkpoint(task: dict[str, Any], worker_id: str, completed: list[str], outputs: dict[str, Any]) -> dict[str, Any]:
    return {"worker_id": worker_id, "completed_steps": list(completed), "outputs": {sid: outputs[sid] for sid in completed}}


def rule_handoff(task: dict[str, Any], variant: str, checkpoint: dict[str, Any] | None) -> dict[str, Any]:
    completed = list((checkpoint or {}).get("completed_steps") or [task["checkpoint_after"]])
    resume = next_step(task["step_ids"], completed) or resume_step_for(task)
    successor = "worker_b" if variant == "intervention" else "worker_a"
    return {"successor": successor, "checkpoint_version": CHECKPOINT_VERSION, "resume_step": resume}


def rule_resume(task: dict[str, Any], worker_id: str, checkpoint: dict[str, Any] | None, handoff: dict[str, Any] | None) -> dict[str, Any]:
    if not handoff:
        return {"worker_id": worker_id, "action": "idle"}
    if worker_id != handoff.get("successor"):
        return {"worker_id": worker_id, "action": "idle"}
    if not checkpoint:
        return {"worker_id": worker_id, "action": "idle"}
    version = str(checkpoint.get("checkpoint_version") or "")
    if version != CHECKPOINT_VERSION:
        return {"worker_id": worker_id, "action": "idle"}
    resume = str(handoff.get("resume_step") or next_step(task["step_ids"], list(checkpoint.get("completed_steps") or [])))
    return {"worker_id": worker_id, "checkpoint_version": version, "resume_step": resume}


def rule_direct(task: dict[str, Any], variant: str) -> dict[str, Any]:
    del variant
    return {"steps": solve_outputs(task)}


def step1_prompt(task: dict[str, Any], private: dict[str, Any]) -> str:
    first = task["step_ids"][0]
    material = private["materials"].get(first)
    return (
        _spec_block(task)
        + "你是 worker_a。现在只执行第一个步骤。\n"
        + '输出 {"worker_id": "worker_a", "step_id": "<id>", "output": {...}}。\n'
        + f"【当前步骤】{first}\n"
        + f"【本步材料】{json.dumps(material, ensure_ascii=False)}\n"
    )


def checkpoint_prompt(task: dict[str, Any], completed: list[str], outputs: dict[str, Any]) -> str:
    return (
        _spec_block(task)
        + "你是 worker_a。提交检查点。不要填写版本号，版本由平台盖章。\n"
        + '输出 {"worker_id": "worker_a", "completed_steps": [...], "outputs": {...}}。\n'
        + f"【已完成步骤】{json.dumps(completed, ensure_ascii=False)}\n"
        + f"【已写入结果】{json.dumps(outputs, ensure_ascii=False)}\n"
    )


def coordinator_prompt(
    task: dict[str, Any],
    variant: str,
    checkpoint: dict[str, Any] | None,
    *,
    a_unavailable: bool,
) -> str:
    body = (
        _spec_block(task)
        + "你是 Coordinator。读取检查点，指定接替者与恢复步骤。不能执行具体步骤，不能给出剩余步骤的正确输出。\n"
        + '输出 {"successor": "worker_a|worker_b", "checkpoint_version": "ckpt-001", "resume_step": "<id>"}。\n'
        + f"【已送达检查点】{json.dumps(checkpoint, ensure_ascii=False)}\n"
    )
    if a_unavailable and variant == "intervention":
        body += f"【状态】{task['interrupt_token']}。Worker A 已不可用，必须指定 worker_b 接替。\n"
    else:
        body += "【状态】Worker A 仍可继续。若检查点有效，指定 worker_a 从下一未完成步骤继续。\n"
    return body


def resume_prompt(
    task: dict[str, Any],
    worker_id: str,
    checkpoint: dict[str, Any] | None,
    handoff: dict[str, Any] | None,
) -> str:
    return (
        _spec_block(task)
        + f"你是 {worker_id}。若未收到接替指令或未收到检查点，输出 {{\"worker_id\": \"{worker_id}\", \"action\": \"idle\"}}。\n"
        + '否则输出 {"worker_id": "<id>", "checkpoint_version": "ckpt-001", "resume_step": "<id>"}。\n'
        + "必须使用与检查点相同的版本。不要重复已完成步骤。\n"
        + f"【检查点】{json.dumps(checkpoint, ensure_ascii=False)}\n"
        + f"【接替指令】{json.dumps(handoff, ensure_ascii=False)}\n"
    )


def successor_step_prompt(
    task: dict[str, Any],
    worker_id: str,
    step_id: str,
    private: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    prior_outputs: dict[str, Any],
) -> str:
    material = (private.get("materials") or {}).get(step_id)
    verify_note = ""
    if task.get("kind") == "receive_verify_archive" and step_id == task["step_ids"][1]:
        verify_note = "核验必须沿用已接收 ID：verified_ids 等于 received_ids，missing_ids 为空列表。禁止编造未出现的 ID。\n"
    if task.get("kind") == "receive_verify_archive" and step_id == task["step_ids"][2]:
        verify_note = "归档使用本步材料中的 folder，sealed 必须为 true。\n"
    return (
        _spec_block(task)
        + f"你是 {worker_id}。只执行当前步骤 {step_id}。不要重复已完成步骤。\n"
        + f'输出 {{"worker_id": "{worker_id}", "step_id": "{step_id}", "output": {{...}}}}。\n'
        + verify_note
        + f"【当前步骤】{step_id}\n"
        + f"【本步材料】{json.dumps(material, ensure_ascii=False)}\n"
        + f"【检查点】{json.dumps(checkpoint, ensure_ascii=False)}\n"
        + f"【已有结果】{json.dumps(prior_outputs, ensure_ascii=False)}\n"
    )


def direct_prompt(task: dict[str, Any], variant: str) -> str:
    outputs = solve_outputs(task)
    first = task["step_ids"][0]
    remaining = task["step_ids"][1:]
    body = (
        _spec_block(task)
        + '输出 {"steps": {"<id>": {字段...}, ...}}。每个步骤的值就是该步结果对象本身，不要包 title，不要再套一层 output。\n'
        + f"【材料】{json.dumps(task['materials'], ensure_ascii=False)}\n"
    )
    if variant == "intervention":
        body += (
            f"【已发生】Worker A 已完成 {first}，结果为 {json.dumps(outputs[first], ensure_ascii=False)}。\n"
            f"只需输出尚未完成的步骤 {json.dumps(remaining, ensure_ascii=False)}，不要重复第一步。\n"
        )
        body += f"【状态】{task['interrupt_token']}\n"
    else:
        body += "Worker A 不中断。必须输出全部三个步骤的最终结果。\n"
    return body
