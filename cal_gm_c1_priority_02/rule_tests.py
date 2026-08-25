#!/usr/bin/env python3
"""Rule calibration for CAL-GM-C1-PRIORITY-02."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cal_gm_c1_priority_02.loader import BANNED, load_tasks, oracle_plan, solve, trap_plan
from cal_gm_c1_priority_02.loop import run_cell
from cal_gm_c1_priority_02.prompts import agent_prompt, rule_agent
from cal_gm_c1_priority_02.scorer import metrics, score_cell
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
        workflow_id="cal_gm_c1_priority_02_rule",
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
        blob = json.dumps(task, default=str, ensure_ascii=False)
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


def test_trap_then_correct_retry():
    task = load_tasks()[0]
    trap = trap_plan(task)
    want = oracle_plan(task, "intervention")

    def gen(prompt: str):
        if "【重试】" in prompt:
            return json.dumps({"assignments": want}, ensure_ascii=False)
        return json.dumps({"assignments": trap}, ensure_ascii=False)

    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", gen)
        cell = _score(task, "intervention", loop)
        assert loop["calls"] == 2
        assert cell["full_pass"] == 1, cell["process_profile"]
        assert "priority_preservation_violation" in loop["retry_prompt"]
        assert want["agent_b"] not in json.dumps((loop["channel"]["inspect"] or {}).get("violations") or [])
        assert "forbid_duplicate_claim" in loop["retry_prompt"]
        assert "禁止把初始冲突方案原样交回" in loop["retry_prompt"]
        assert loop["leaked_repair_slot_in_nack"] is False


def test_trap_then_restore_conflict_still_fails():
    task = load_tasks()[0]
    trap = trap_plan(task)
    initial = {"agent_a": task["agent_a"]["preferred"], "agent_b": task["agent_b"]["intervention"]["preferred"]}

    def gen(prompt: str):
        if "【重试】" in prompt:
            return json.dumps({"assignments": initial}, ensure_ascii=False)
        return json.dumps({"assignments": trap}, ensure_ascii=False)

    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", gen)
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "final_state_conflict"


def test_trap_moves_high_priority_nack():
    task = load_tasks()[0]
    trap = trap_plan(task)
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps({"assignments": trap}))
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        nack = loop["retry_prompt"]
        assert "priority_preservation_violation" in nack
        assert trap["agent_b"] not in json.dumps({"v": json.loads(nack.split("【违规证据】", 1)[1].split("\n", 1)[0])})
        assert loop["leaked_repair_slot_in_nack"] is False


def test_inspect_no_repair_slot():
    task = load_tasks()[0]
    repair = task["oracle"]["intervention"]["assignments"]["agent_b"]
    clash = {"agent_a": task["slots"][0], "agent_b": task["slots"][0]}
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps({"assignments": clash}))
        blob = json.dumps(loop["channel"]["inspect"])
        assert "duplicate_resource_claim" in blob
        assert repair not in blob


def test_conflict_field_rejected():
    task = load_tasks()[0]
    want = oracle_plan(task, "control")
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "control", lambda _p: json.dumps({"assignments": want, "conflict": False}))
        cell = _score(task, "control", loop)
        assert loop["contract_error"] == "conflict_field_not_allowed"
        assert cell["full_pass"] == 0


def main() -> int:
    test_oracle_matches()
    print("oracle matches priority keep then earliest idle")
    test_not_old_items()
    print("new instances, not C1-01/COMP/REPAIR/C1-02/PRIORITY-01")
    test_rule_pass()
    print("Rule control+intervention pass")
    test_trap_then_correct_retry()
    print("trap then correct retry passes; nack does not name B slot")
    test_trap_then_restore_conflict_still_fails()
    print("restoring duplicate after nack still fails")
    test_trap_moves_high_priority_nack()
    print("moving high-priority is caught")
    test_inspect_no_repair_slot()
    print("inspect does not leak repair slot")
    test_conflict_field_rejected()
    print("conflict field rejected")
    print("CAL-GM-C1-PRIORITY-02 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
