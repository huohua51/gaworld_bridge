from __future__ import annotations

from typing import Any

from holdout_l1.loader import BANNED, leak_tokens_for, load_tasks, worker_private
from holdout_l1.loop import ORACLE_MARKERS
from holdout_l1.prompts import checkpoint_prompt, coordinator_prompt, direct_prompt, resume_prompt, step1_prompt, successor_step_prompt

CALL_CONTRACT = {
    "direct": ["一次调用看到完整步骤并输出三步结果；非正式结果"],
    "multi": [
        "A 执行第一步并形成平台盖章检查点",
        "Coordinator 确认检查点；intervention 将接替任务分配给 B",
        "接替者从检查点继续，不重复已完成工作",
    ],
    "drop_checkpoint": [
        "A 仍产生检查点",
        "只丢 B 的检查点副本",
        "B 在 intervention 仍运行；control 由 A 继续应成功",
    ],
    "drop_handoff": [
        "Coordinator 仍运行",
        "接替指令不送达 B",
        "control 由 A 继续应成功；intervention 应失败",
    ],
}


def preflight() -> dict[str, Any]:
    leaks = []
    for task in load_tasks():
        blob = str(task)
        for token in BANNED:
            if token in blob:
                leaks.append({"where": "banned_item", "task": task["id"], "token": token})
        private_a = worker_private(task, "worker_a")
        private_b = worker_private(task, "worker_b")
        token = task["interrupt_token"]
        s1 = step1_prompt(task, private_a)
        ck = checkpoint_prompt(task, [task["step_ids"][0]], {task["step_ids"][0]: task["materials"][task["step_ids"][0]]})
        coord_c = coordinator_prompt(task, "control", {"checkpoint_version": "ckpt-001", "completed_steps": [task["step_ids"][0]]}, a_unavailable=False)
        coord_i = coordinator_prompt(task, "intervention", {"checkpoint_version": "ckpt-001", "completed_steps": [task["step_ids"][0]]}, a_unavailable=True)
        resume_b = resume_prompt(task, "worker_b", {"checkpoint_version": "ckpt-001", "completed_steps": [task["step_ids"][0]]}, {"successor": "worker_b", "checkpoint_version": "ckpt-001", "resume_step": task["step_ids"][1]})
        step2 = successor_step_prompt(task, "worker_b", task["step_ids"][1], private_b, {"checkpoint_version": "ckpt-001"}, {})
        direct_c = direct_prompt(task, "control")
        direct_i = direct_prompt(task, "intervention")
        if token in s1 or token in ck or token in coord_c or token in direct_c:
            leaks.append({"where": "interrupt_in_control_or_a", "task": task["id"], "token": token})
        if token not in coord_i or token not in direct_i:
            leaks.append({"where": "interrupt_missing_intervention", "task": task["id"], "token": token})
        remaining = task["step_ids"][1]
        if remaining in s1:
            pass
        for marker in ORACLE_MARKERS:
            if marker in s1 + ck + coord_i + resume_b + step2 + direct_i:
                leaks.append({"where": "oracle", "task": task["id"], "token": marker})
        if "remaining_outputs" in coord_i or "suggested_output" in coord_i:
            leaks.append({"where": "coordinator_named_remaining", "task": task["id"], "token": "remaining"})
        want2 = task["oracle"]["intervention"]["outputs"][task["step_ids"][1]]
        if json_dump(want2) in coord_i:
            leaks.append({"where": "handoff_has_step2_output", "task": task["id"], "token": "step2"})
        if private_a["materials"] != private_b["materials"]:
            leaks.append({"where": "backup_materials_mismatch", "task": task["id"], "token": "materials"})
        if leak_tokens_for(task, "control"):
            leaks.append({"where": "control_leak_tokens", "task": task["id"], "token": "control"})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "call_contract": CALL_CONTRACT,
        "logical_calls_per_matrix_cell": 6,
        "environment_rewrites_world": False,
        "coordinator_executes": False,
        "primary_track": "multi",
    }


def json_dump(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)
