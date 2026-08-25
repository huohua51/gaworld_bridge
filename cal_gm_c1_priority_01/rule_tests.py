#!/usr/bin/env python3
"""Rule calibration for CAL-GM-C1-PRIORITY-01."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cal_gm_c1_priority_01.loader import BANNED, load_tasks, oracle_plan, solve, trap_plan
from cal_gm_c1_priority_01.loop import run_cell
from cal_gm_c1_priority_01.prompts import agent_prompt, rule_agent
from cal_gm_c1_priority_01.scorer import metrics, score_cell
from gaworld.work.coordination import actual_final_conflict_free

VARIANTS = ("control", "intervention")


def _run(tmp: Path, task: dict, variant: str, generate_fn):
    return run_cell(
        task=task,
        variant=variant,
        instance_id=f"{task['id']}_{variant}_rule",
        out_dir=tmp / f"{task['id']}_{variant}",
        generate_fn=generate_fn,
    )


def _score(task: dict, variant: str, loop: dict) -> dict:
    return score_cell(
        task=task,
        variant=variant,
        repeat_id=0,
        loop=loop,
        workflow_id="cal_gm_c1_priority_01_rule",
        instance_id=loop["instance_id"],
    )


def test_oracle_matches():
    for task in load_tasks():
        for variant in VARIANTS:
            want = oracle_plan(task, variant)
            assert solve(task, variant) == want
            assert actual_final_conflict_free(want) is True
            assert want["agent_a"] == task["agent_a"]["preferred"]


def test_not_old_items():
    for task in load_tasks():
        blob = json.dumps(task, default=str)
        for token in BANNED:
            assert token not in blob, token
        for variant in VARIANTS:
            prompt = agent_prompt(task, variant)
            for token in BANNED:
                assert token not in prompt, token


def test_rule_pass():
    cells = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in VARIANTS:
                loop = _run(tmp, task, variant, lambda _p, t=task, v=variant: json.dumps(rule_agent(t, v), ensure_ascii=False))
                cell = _score(task, variant, loop)
                cells.append(cell)
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])
                assert loop["calls"] == 1
                assert loop["env_denied"] is True
                assert loop["channel"]["unregistered_modification"] == 0
    summary = metrics(cells)
    assert summary["pass_gate"]["holds"] is True, summary


def test_trap_moves_high_priority():
    task = load_tasks()[0]
    trap = trap_plan(task)
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps({"assignments": trap}))
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "priority_preservation_violation"
        nack = json.dumps((loop["channel"]["propose"] or {}).get("violations") or [])
        assert "priority_preservation_violation" in nack
        assert trap["agent_b"] not in nack
        assert task["oracle"]["intervention"]["assignments"]["agent_b"] not in nack
        assert loop["leaked_repair_slot_in_nack"] is False


def test_inspect_no_repair_slot():
    task = load_tasks()[0]
    repair = task["oracle"]["intervention"]["assignments"]["agent_b"]
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps({"assignments": {"agent_a": "ac21", "agent_b": "ac21"}}))
        blob = json.dumps(loop["channel"]["inspect"])
        assert "duplicate_resource_claim" in blob
        assert repair not in blob


def test_conflict_field_rejected():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "control", lambda _p: json.dumps({"assignments": {"agent_a": "ac21", "agent_b": "ac22"}, "conflict": False}))
        cell = _score(task, "control", loop)
        assert loop["contract_error"] == "conflict_field_not_allowed"
        assert cell["full_pass"] == 0


def main() -> int:
    test_oracle_matches()
    print("oracle matches priority keep then earliest idle")
    test_not_old_items()
    print("new instances, not C1-01/COMP/REPAIR/C1-02")
    test_rule_pass()
    print("Rule control+intervention pass")
    test_trap_moves_high_priority()
    print("moving high-priority is caught; nack does not name B slot")
    test_inspect_no_repair_slot()
    print("inspect does not leak repair slot")
    test_conflict_field_rejected()
    print("conflict field rejected")
    print("CAL-GM-C1-PRIORITY-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
