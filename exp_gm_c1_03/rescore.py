"""Offline rescore of frozen C1-03 seed0 cells. Does not call the model."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from exp_gm_c1_03.contract import INITIAL_VERSION, PLAN_VERSION, commit_contract, parse_json_object, plan_contract, report_contract
from exp_gm_c1_03.loader import load_task
from exp_gm_c1_03.scorer import score_cell
from v0_first_batch.paths import BRIDGE_ROOT

OUT = BRIDGE_ROOT / "output" / "exp_gm_c1_03_20260825"
WORKFLOW_ID = "exp_gm_c1_03_retry"


def _gates(cell: dict) -> dict[str, bool]:
    return {str(item.get("gate_id")): bool(item.get("passed")) for item in cell.get("gates") or []}


def loop_from_run(run_dir: Path, task: dict, cell: dict) -> dict:
    extra = dict(cell.get("extra") or {})
    profile = dict(cell.get("process_profile") or {})
    raw = json.loads((run_dir / "raw.json").read_text(encoding="utf-8"))
    report_a, err_a = report_contract(parse_json_object(raw.get("report_a") or ""), agent_id="agent_a")
    report_b, err_b = report_contract(parse_json_object(raw.get("report_b") or ""), agent_id="agent_b")
    initial, initial_err = plan_contract(parse_json_object(raw.get("initial") or ""), version=INITIAL_VERSION)
    plan, plan_err = plan_contract(parse_json_object(raw.get("plan") or ""), version=PLAN_VERSION)
    commit_a, err_ca = commit_contract(parse_json_object(raw.get("commit_a") or ""), agent_id="agent_a")
    commit_b, err_cb = commit_contract(parse_json_object(raw.get("commit_b") or ""), agent_id="agent_b")
    gates = _gates(cell)
    track = str(extra.get("track") or "")
    return {
        "track": track,
        "variant": extra.get("variant"),
        "events": profile.get("events") or [],
        "budget": profile.get("budget") or {},
        "budget_valid": bool((profile.get("budget") or {}).get("valid")),
        "reports": {"agent_a": report_a, "agent_b": report_b},
        "report_errors": {"agent_a": err_a, "agent_b": err_b},
        "initial_plan": initial,
        "initial_error": initial_err,
        "plan": plan,
        "plan_error": plan_err,
        "commits": {"agent_a": commit_a, "agent_b": commit_b},
        "commit_errors": {"agent_a": err_ca, "agent_b": err_cb},
        "world": profile.get("world") or {},
        "world_path": str(run_dir),
        "violations": profile.get("violations") or [],
        "nack_path": bool(extra.get("nack_path_coverage")),
        "protection_delivered": bool(extra.get("protection_delivered")),
        "ja_accepted": False,
        "unregistered_modification": int(extra.get("unregistered_modification") or 0),
        "a_ran": True,
        "b_ran": bool(extra.get("b_ran", True)),
        "coordinator_ran": True,
        "plan_delivered": bool(extra.get("plan_delivered")),
        "drop_protection_isolated": track != "drop_protection" or not extra.get("protection_delivered"),
        "drop_coordinator_isolated": track != "drop_coordinator" or not extra.get("plan_delivered"),
        "peek_denied": bool(gates.get("private_isolated", True)),
        "env_denied": bool(gates.get("environment_did_not_rewrite", True)),
        "coordinator_exec_denied": bool(gates.get("coordinator_did_not_execute", True)),
        "leaks": [],
        "leaked_repair_slot_in_nack": not bool(gates.get("nack_did_not_leak_repair_slot", True)),
        "oracle_in_prompt": [] if gates.get("oracle_not_in_prompts", True) else ["oracle"],
        "first_assignments": extra.get("first_assignments") or dict((initial or {}).get("assignments") or {}),
        "retry_assignments": dict((plan or {}).get("assignments") or {}),
    }


def rescore_seed0() -> list[dict]:
    cells = []
    for run_dir in sorted((OUT / "runs").glob("*_r0")):
        if not (run_dir / "raw.json").is_file() or not (run_dir / "cell_result.json").is_file():
            continue
        prior = json.loads((run_dir / "cell_result.json").read_text(encoding="utf-8"))
        extra = prior.get("extra") or {}
        if extra.get("track") == "direct":
            continue
        backup = run_dir / "cell_result.pre_planid_rescore.json"
        if not backup.is_file():
            shutil.copy(run_dir / "cell_result.json", backup)
        task = load_task(str(extra["task_id"]))
        loop = loop_from_run(run_dir, task, prior)
        cell = score_cell(
            task=task,
            variant=str(extra["variant"]),
            track=str(extra["track"]),
            repeat_id=int(extra.get("repeat_id") or 0),
            loop=loop,
            workflow_id=WORKFLOW_ID,
            instance_id=str(prior.get("instance_id") or run_dir.name),
        )
        extra2 = dict(cell.get("extra") or {})
        extra2["mode"] = extra.get("mode")
        extra2["model_version"] = extra.get("model_version")
        extra2["rescored"] = "plan_id_audit"
        cell["extra"] = extra2
        cell["ranking_eligible"] = False
        (run_dir / "cell_result.json").write_text(json.dumps(cell, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cells.append(cell)
    return cells
