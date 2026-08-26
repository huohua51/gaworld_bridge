"""Load and validate registered T5 policy tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONDITIONS = ("no_policy", "real_policy", "placebo_policy")
TRACKS = ("full", "disconnect_policy")


def load_tasks() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("tasks.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tasks = list(payload.get("tasks") or [])
    for task in tasks:
        residents = list(task.get("residents") or [])
        resident_ids = [str(item.get("agent_id") or "") for item in residents]
        groups = {str(item.get("group") or "") for item in residents}
        targets = {str(item) for item in task.get("target_groups") or []}
        actions = dict(task.get("action_effects") or {})
        if not residents or len(resident_ids) != len(set(resident_ids)):
            raise ValueError(f"invalid population for {task.get('id')}")
        if not targets or not targets <= groups:
            raise ValueError(f"invalid target groups for {task.get('id')}")
        if task.get("target_action") not in actions or "keep_current" not in actions:
            raise ValueError(f"invalid action registry for {task.get('id')}")
        if int(task.get("effective_step") or -1) < 0:
            raise ValueError(f"invalid effective step for {task.get('id')}")
    return tasks
