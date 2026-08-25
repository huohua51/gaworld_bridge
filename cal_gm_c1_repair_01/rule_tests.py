#!/usr/bin/env python3
"""Rule calibration for CAL-GM-C1-REPAIR-01. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cal_gm_c1_repair_01.loader import BANNED, given_final, initial_conflict, load_tasks, oracle_value, solve_reallocate
from cal_gm_c1_repair_01.loop import run_cell
from cal_gm_c1_repair_01.prompts import agent_prompt, rule_agent
from cal_gm_c1_repair_01.scorer import metrics, score_cell
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
        workflow_id="cal_gm_c1_repair_01_rule",
        instance_id=loop["instance_id"],
    )


def test_oracle_matches_scorer():
    for task in load_tasks():
        for variant in VARIANTS:
            want = oracle_value(task, variant)
            if task["component"] == "A":
                assert initial_conflict(task, variant) is want
            elif task["component"] == "B":
                assert actual_final_conflict_free(given_final(task, variant)) is want
            else:
                assert solve_reallocate(task, variant) == want
                assert actual_final_conflict_free(want) is True


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
                if task["component"] == "C":
                    assert loop["calls"] == 1
                    assert loop["channel"]["unregistered_modification"] == 0
                    assert loop["channel"]["actual_final_conflict_free"] is True
    summary = metrics(cells)
    assert summary["pass_gate"]["holds"] is True, summary
    assert summary["c1_02_allowed"] is True


def test_wrong_boolean():
    tasks = {task["component"]: task for task in load_tasks()}
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        loop = _run(tmp, tasks["B"], "control", lambda _p: json.dumps({"final_plan_conflict_free": False}))
        cell = _score(tasks["B"], "control", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "self_assessment_incorrect"
        extra = cell["extra"]
        assert extra["actual_final_conflict_free"] is True
        assert extra["self_assessment_correct"] is False
        assert extra["assessment_execution_gap"] == 1


def test_c_keeps_conflict():
    task = next(t for t in load_tasks() if t["component"] == "C")
    with tempfile.TemporaryDirectory() as raw:
        payload = {"assignments": {"agent_a": "k1", "agent_b": "k1"}}
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps(payload))
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        assert loop["channel"]["actual_final_conflict_free"] is False
        assert cell["process_profile"]["first_error"] == "allocation_incorrect"


def test_c_rejects_conflict_field():
    task = next(t for t in load_tasks() if t["component"] == "C")
    with tempfile.TemporaryDirectory() as raw:
        payload = {"assignments": {"agent_a": "k1", "agent_b": "k2"}, "conflict": True}
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps(payload))
        cell = _score(task, "intervention", loop)
        assert loop["contract_error"] == "conflict_field_not_allowed"
        assert cell["full_pass"] == 0


def test_inspect_does_not_leak_oracle_slot():
    task = next(t for t in load_tasks() if t["component"] == "C")
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps({"assignments": {"agent_a": "k1", "agent_b": "k1"}}))
        inspect = loop["channel"]["inspect"]
        blob = json.dumps(inspect)
        assert "k2" not in blob
        assert "duplicate_resource_claim" in blob


def test_not_old_items():
    for task in load_tasks():
        blob = json.dumps(task, default=str)
        for token in BANNED:
            assert token not in blob, token
        for variant in VARIANTS:
            prompt = agent_prompt(task, variant)
            for token in BANNED:
                assert token not in prompt, token


def main() -> int:
    test_oracle_matches_scorer()
    print("oracle matches scorer-computed facts")
    test_not_old_items()
    print("new instances, not C1-01 / C1-COMP-01")
    test_rule_pass()
    print("Rule A/B/C control+intervention pass")
    test_wrong_boolean()
    print("B wrong boolean: self-assessment gap, world fact still true")
    test_c_keeps_conflict()
    print("C duplicate kept: world still conflicted")
    test_c_rejects_conflict_field()
    print("C rejects conflict field")
    test_inspect_does_not_leak_oracle_slot()
    print("inspect does not leak repair slot")
    print("CAL-GM-C1-REPAIR-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
