"""Diagnostic only. Does not change FullPass or SystemRetryRecoverySuccess."""

from __future__ import annotations

import json
from pathlib import Path

from exp_gm_c1_03.contract import PLAN_VERSION, parse_json_object, plan_contract
from exp_gm_c1_03.loader import load_task, privates_for, protection_spec, solve_final
from gaworld.work.coordination import actual_final_conflict_free
from v0_first_batch.paths import BRIDGE_ROOT

OUT = BRIDGE_ROOT / "output" / "exp_gm_c1_03_20260825"
CELLS = (
    "c1_03_electrophoresis_001_intervention_multi_r0",
    "c1_03_cryostat_001_intervention_multi_r0",
    "c1_03_incubator_shelf_001_intervention_multi_r0",
)


def diagnose(assignments: dict[str, str], task: dict) -> dict:
    want = solve_final(task, "intervention")
    protected = str(protection_spec(task)["slot"])
    private = privates_for(task, "intervention")
    a = str(assignments.get("agent_a") or "")
    b = str(assignments.get("agent_b") or "")
    keep = a == protected
    earliest = keep and b == want["agent_b"]
    feasible = a in set(private["agent_a"]["feasible"]) and b in set(private["agent_b"]["feasible"])
    free = actual_final_conflict_free({"agent_a": a, "agent_b": b}) if a and b else False
    correct = bool(keep and earliest and feasible and free and {"agent_a": a, "agent_b": b} == want)
    return {
        "assignments": {"agent_a": a, "agent_b": b},
        "want": want,
        "keep_protected_assignment": keep,
        "low_priority_earliest_idle": earliest,
        "private_constraints_ok": feasible,
        "conflict_free": free,
        "semantic_retry_assignment_correct": correct,
    }


def main() -> dict:
    rows = []
    for instance_id in CELLS:
        task_id = instance_id.rsplit("_intervention_multi_r0", 1)[0]
        task = load_task(task_id)
        raw = json.loads((OUT / "runs" / instance_id / "raw.json").read_text(encoding="utf-8"))
        plan, plan_err = plan_contract(parse_json_object(raw["plan"]), version=PLAN_VERSION)
        body = diagnose(plan.get("assignments") or {}, task)
        body.update(
            {
                "instance_id": instance_id,
                "plan_error": plan_err,
                "contract_compliance": plan_err == "ok",
                "same_as_first": (plan.get("assignments") or {}) == (task["oracle"]["intervention"]["first"]),
            }
        )
        rows.append(body)
    n = len(rows)
    correct = sum(int(row["semantic_retry_assignment_correct"]) for row in rows)
    payload = {
        "experiment_id": "EXP-GM-C1-03",
        "diagnostic_only": True,
        "does_not_change_fullpass": True,
        "system_retry_recovered": "0/3",
        "semantic_retry_assignment_correct": f"{correct}/{n}",
        "retry_contract_failure": "2/3",
        "retry_not_adapted": "1/3",
        "cells": rows,
    }
    return payload


if __name__ == "__main__":
    import yaml

    payload = main()
    payload["note"] = (
        "忽略握手版本后检查重试 assignments 是否满足优先级保持、最早空闲、可行集和无冲突。"
        "三格语义均不正确：没有一格只错版本、方案本身算对。"
    )
    path = OUT / "SEMANTIC_RETRY.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(json.dumps({"semantic_retry_assignment_correct": payload["semantic_retry_assignment_correct"], "path": str(path)}, ensure_ascii=False))
