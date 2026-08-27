"""Load and validate T5-v2 explicit policy-semantics tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

POLICY_STATES = ("absence", "binding", "nonbinding")
TRACKS = ("full", "disconnect_policy")


def load_tasks() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("tasks.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tasks = list(payload.get("tasks") or [])
    if not tasks:
        raise ValueError("T5-v2 requires registered tasks")
    seen: set[str] = set()
    for task in tasks:
        task_id = str(task.get("id") or "")
        if not task_id or task_id in seen:
            raise ValueError(f"invalid or duplicate task id: {task_id}")
        seen.add(task_id)
        residents = list(task.get("residents") or [])
        resident_ids = [str(item.get("agent_id") or "") for item in residents]
        groups = {str(item.get("group") or "") for item in residents}
        targets = {str(item) for item in task.get("target_groups") or []}
        actions = dict(task.get("action_effects") or {})
        if len(residents) != 4 or len(resident_ids) != len(set(resident_ids)):
            raise ValueError(f"invalid population for {task_id}")
        if not targets or not targets <= groups:
            raise ValueError(f"invalid target groups for {task_id}")
        if task.get("target_action") not in actions or "keep_current" not in actions:
            raise ValueError(f"invalid action registry for {task_id}")
        if int(task.get("effective_step") or -1) < 0:
            raise ValueError(f"invalid effective step for {task_id}")
    return tasks
