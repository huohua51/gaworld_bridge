"""L1-01 tasks. Not C1 / T3 / N1 / OA items."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
TASK_IDS = ("l1_ho_crane_load_001", "l1_ho_fridge_log_001", "l1_ho_mail_bay_001")
TRACKS = ("multi", "drop_checkpoint", "drop_handoff")
VARIANTS = ("control", "intervention")
RULE_TEXT = (
    "步骤必须按顺序执行。已完成步骤不得重复、不得覆盖。"
    "检查点由平台盖章为 ckpt-001。"
    "接替者必须读取同一版本检查点，从下一个未完成步骤继续。"
    "Coordinator 只确认检查点并指定接替者，不能代为执行。"
)
BANNED = (
    "c1_03_electrophoresis_001",
    "c1_03_cryostat_001",
    "c1_03_incubator_shelf_001",
    "c1_02_optics_table_001",
    "c1_02_greenhouse_001",
    "c1_02_cold_store_001",
    "c1prio_mass_spec_001",
    "c1prio2_hplc_001",
    "et81",
    "cy91",
    "ic81",
    "w08",
    "ms41",
    "n1_bridge_status_001",
    "n1_ferry_status_001",
    "n1_warehouse_gate_001",
    "t3_alert_celsius_001",
    "t3_redeem_points_001",
    "t3_free_ship_kg_001",
    "plan-002",
    "optics_table",
    "l1_01_specimen_log_001",
    "l1_01_inventory_lots_001",
    "l1_01_centrifuge_rotor_001",
    "l1_01b_file_intake_001",
    "l1res_mail_sort_001",
    "l1res_pump_prime_001",
    "l1res_badge_print_001",
    "intake_sp71",
    "verify_sp71",
    "archive_sp71",
    "lot_px41",
    "rotor_cf21",
    "file_rx41",
    "mail_in11",
    "pump_fill21",
    "badge_draft31",
    "l1_01c_gas_cylinder_001",
    "l1_01c_balance_check_001",
    "l1_01c_label_intake_001",
    "gas_cy11",
    "bal_ck21",
    "label_rx51",
    "L9",
    "SP-771",
)


def load_task(task_id: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / "tasks" / f"{task_id}.yaml").read_text(encoding="utf-8"))
    payload["oracle_path"] = ROOT / "oracle" / f"{task_id}.json"
    payload["oracle"] = json.loads(payload["oracle_path"].read_text(encoding="utf-8"))
    payload["step_ids"] = [str(item["id"]) for item in payload["steps"]]
    return payload


def load_tasks() -> list[dict[str, Any]]:
    return [load_task(task_id) for task_id in TASK_IDS]


def leak_tokens_for(task: dict[str, Any], variant: str) -> list[str]:
    if variant != "intervention":
        return []
    return [str(task["interrupt_token"])]


def public_spec(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task["id"],
        "title": task["title"],
        "rule": task["rule"],
        "rule_text": RULE_TEXT,
        "steps": [{"id": item["id"], "title": item["title"]} for item in task["steps"]],
        "checkpoint_after": task["checkpoint_after"],
        "checkpoint_version": "ckpt-001",
        "output_rule": str(task.get("output_rule") or ""),
    }


def worker_private(task: dict[str, Any], worker: str) -> dict[str, Any]:
    return {
        "worker_id": worker,
        "materials": dict(task["materials"]),
        "verify_prefix": str(task.get("verify_prefix") or ""),
    }


def _file_verify(task: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    recv_id = task["step_ids"][0]
    received = outputs.get(recv_id) or task["materials"][recv_id]
    return {"verified_ids": list(received["received_ids"]), "missing_ids": []}


def _file_archive(task: dict[str, Any]) -> dict[str, Any]:
    archive = dict(task["materials"][task["step_ids"][2]])
    archive["sealed"] = True
    return archive


def solve_outputs(task: dict[str, Any]) -> dict[str, Any]:
    step_ids = task["step_ids"]
    outputs: dict[str, Any] = {}
    if task.get("kind") == "receive_verify_archive":
        outputs[step_ids[0]] = dict(task["materials"][step_ids[0]])
        outputs[step_ids[1]] = _file_verify(task, outputs)
        outputs[step_ids[2]] = _file_archive(task)
        return outputs
    for step_id in step_ids:
        outputs[step_id] = dict(task["materials"][step_id])
    return outputs


def solve_step(task: dict[str, Any], step_id: str, prior: dict[str, Any] | None = None) -> dict[str, Any]:
    outputs = dict(prior or {})
    full = solve_outputs(task)
    if step_id not in full:
        return {}
    if task.get("kind") == "receive_verify_archive" and step_id == task["step_ids"][1]:
        return _file_verify(task, outputs)
    if task.get("kind") == "receive_verify_archive" and step_id == task["step_ids"][2]:
        return _file_archive(task)
    return dict(full[step_id])


def oracle_plan(task: dict[str, Any], variant: str) -> dict[str, Any]:
    return dict(task["oracle"][variant])


def resume_step_for(task: dict[str, Any]) -> str:
    return str(task["step_ids"][1])
