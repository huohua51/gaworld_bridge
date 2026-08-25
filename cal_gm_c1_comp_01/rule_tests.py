#!/usr/bin/env python3
"""Rule calibration for CAL-GM-C1-COMP-01. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cal_gm_c1_comp_01.loader import BANNED, final_conflict_free, initial_conflict, load_tasks, oracle_value, solve_reallocate
from cal_gm_c1_comp_01.loop import run_cell
from cal_gm_c1_comp_01.prompts import agent_prompt, rule_agent
from cal_gm_c1_comp_01.scorer import metrics, score_cell

VARIANTS = ("control", "intervention")


def _run(tmp: Path, task: dict, variant: str, generate_fn):
    return run_cell(
        task=task,
        variant=variant,
        instance_id=f"{task['id']}_{variant}_rule",
        out_dir=tmp / f"{task['id']}_{variant}",
        prompt=agent_prompt(task, variant),
        generate_fn=generate_fn,
    )


def _score(task: dict, variant: str, loop: dict) -> dict:
    return score_cell(
        task=task,
        variant=variant,
        repeat_id=0,
        loop=loop,
        workflow_id="cal_gm_c1_comp_01_rule",
        instance_id=loop["instance_id"],
    )


def test_oracle_matches_scorer():
    for task in load_tasks():
        for variant in VARIANTS:
            want = oracle_value(task, variant)
            if task["component"] == "A":
                assert initial_conflict(task, variant) is want
            elif task["component"] == "B":
                assert final_conflict_free(task, variant) is want
            else:
                assert solve_reallocate(task, variant) == want


def test_rule_pass():
    cells = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in VARIANTS:
                loop = _run(tmp, task, variant, lambda _p, t=task, v=variant: json.dumps(rule_agent(t, v), ensure_ascii=False))
                cell = _score(task, variant, loop)
                cells.append(cell)
                assert loop["contract_error"] == "ok", (task["id"], variant, loop)
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])
    summary = metrics(cells)
    assert summary["pass_gate"]["holds"] is True, summary


def test_wrong_boolean():
    tasks = {task["component"]: task for task in load_tasks()}
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        loop = _run(tmp, tasks["A"], "control", lambda _p: json.dumps({"initial_conflict_detected": True}))
        cell = _score(tasks["A"], "control", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "initial_conflict_incorrect"
        loop = _run(tmp, tasks["B"], "intervention", lambda _p: json.dumps({"final_plan_conflict_free": True}))
        cell = _score(tasks["B"], "intervention", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "final_conflict_free_incorrect"


def test_c_rejects_conflict_field():
    task = next(t for t in load_tasks() if t["component"] == "C")
    with tempfile.TemporaryDirectory() as raw:
        payload = {"assignments": {"agent_a": "h8", "agent_b": "h9"}, "conflict": True}
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps(payload))
        cell = _score(task, "intervention", loop)
        assert loop["contract_error"] == "conflict_field_not_allowed"
        assert cell["full_pass"] == 0


def test_c_wrong_allocation():
    task = next(t for t in load_tasks() if t["component"] == "C")
    with tempfile.TemporaryDirectory() as raw:
        payload = {"assignments": {"agent_a": "h8", "agent_b": "h8"}}
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps(payload))
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "allocation_incorrect"


def test_not_c1_01():
    for task in load_tasks():
        blob = json.dumps(task, default=str)
        for token in BANNED:
            assert token not in blob, token
        for variant in VARIANTS:
            prompt = agent_prompt(task, variant)
            assert "\"conflict\"" not in prompt or task["component"] == "C"
            if task["component"] != "C":
                assert " conflict" not in prompt.lower() or "初始" in prompt or "最终" in prompt
            for token in BANNED:
                assert token not in prompt


def test_a_control_not_same_slot():
    task = next(t for t in load_tasks() if t["component"] == "A")
    prompt = agent_prompt(task, "control")
    assert "bay-2" in prompt
    assert prompt.count("bay-1") == 1


def main() -> int:
    test_oracle_matches_scorer()
    print("oracle matches scorer-computed facts")
    test_not_c1_01()
    print("new instances, not C1-01 items")
    test_rule_pass()
    print("Rule A/B/C control+intervention pass")
    test_wrong_boolean()
    print("wrong boolean: fail-as-expected")
    test_c_rejects_conflict_field()
    print("C rejects conflict field")
    test_c_wrong_allocation()
    print("C duplicate allocation: allocation_incorrect")
    test_a_control_not_same_slot()
    print("A control shows different initial slots")
    print("CAL-GM-C1-COMP-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
