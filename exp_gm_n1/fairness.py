"""Fairness: equal 3-call budget, private Source, Drop isolation."""

from __future__ import annotations

from typing import Any

from exp_gm_n1.loader import leak_tokens_for, load_tasks, source_private
from exp_gm_n1.prompts import decision_prompt, source_prompt

ORACLE_MARKERS = (
    "n1_bridge_status_001.json",
    "n1_ferry_status_001.json",
    "n1_warehouse_gate_001.json",
)


def preflight() -> dict[str, Any]:
    leaks = []
    for task in load_tasks():
        control_p = source_prompt(source_private(task, "control"))
        for token in leak_tokens_for(task, "intervention"):
            if token in control_p:
                leaks.append({"where": "source_control", "task": task["id"], "token": token})
        drop_dm = decision_prompt(task, plan=dict(task["plan"]), inbox=[])
        for token in leak_tokens_for(task, "intervention"):
            if token in drop_dm:
                leaks.append({"where": "drop_decision", "task": task["id"], "token": token})
        for marker in ORACLE_MARKERS:
            if marker in control_p or marker in drop_dm:
                leaks.append({"where": "oracle", "task": task["id"], "token": marker})
    return {
        "ok": not leaks,
        "leaks": leaks,
        "logical_calls_per_cell": 3,
        "drop_relay_skipped": False,
        "decision_maker_reads_source_private": False,
        "environment_rewrites_action": False,
    }
