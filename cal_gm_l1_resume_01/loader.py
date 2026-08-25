"""New three-step flows. Not L1-01 / L1-01b / C1 / T3 / N1 items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from gaworld.work.continuity import next_step

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("l1res_mail_sort_001", "l1res_pump_prime_001", "l1res_badge_print_001")
VARIANTS = ("control", "intervention")
BANNED = (
    "l1_01_inventory_lots_001",
    "l1_01_centrifuge_rotor_001",
    "l1_01b_file_intake_001",
    "l1_01_specimen_log_001",
    "lot_px41",
    "rotor_cf21",
    "file_rx41",
    "verify_sp71",
    "checksum",
)


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["oracle_path"] = ROOT / "oracle" / f"{task_id}.json"
    payload["oracle"] = json.loads(payload["oracle_path"].read_text(encoding="utf-8"))
    payload["step_ids"] = [str(item["id"]) for item in payload["steps"]]
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def want_resume(task: dict[str, Any]) -> dict[str, Any]:
    step_ids = list(task["step_ids"])
    completed = [step_ids[0]]
    resume = next_step(step_ids, completed)
    remaining = [sid for sid in step_ids if sid not in set(completed)]
    return {"completed_steps": completed, "resume_step": resume, "remaining_steps": remaining}


def checkpoint_for(task: dict[str, Any], variant: str) -> dict[str, Any]:
    step_ids = list(task["step_ids"])
    completed = [step_ids[0]]
    if variant == "control":
        outputs = {step_ids[0]: {"status": "done"}}
    else:
        outputs = {step_ids[1]: {"status": "placeholder"}, step_ids[2]: {"status": "placeholder"}}
    return {
        "checkpoint_version": "ckpt-001",
        "completed_steps": completed,
        "outputs": outputs,
    }
