#!/usr/bin/env python3
"""Rule calibration for CAL-GM-L1-RESUME-01. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cal_gm_l1_resume_01.loader import BANNED, checkpoint_for, load_tasks, want_resume
from cal_gm_l1_resume_01.loop import run_cell
from cal_gm_l1_resume_01.prompts import agent_prompt, rule_agent
from cal_gm_l1_resume_01.scorer import metrics, score_cell
from gaworld.work.continuity import next_step

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
        workflow_id="cal_gm_l1_resume_01_rule",
        instance_id=loop["instance_id"],
    )


def test_new_tasks_not_l1():
    ids = {task["id"] for task in load_tasks()}
    assert ids == {"l1res_mail_sort_001", "l1res_pump_prime_001", "l1res_badge_print_001"}
    blob = json.dumps([load_tasks()], default=str)
    for token in BANNED:
        assert token not in blob, token


def test_oracle_matches_platform_next_step():
    for task in load_tasks():
        want = want_resume(task)
        assert want["resume_step"] == next_step(task["step_ids"], want["completed_steps"])
        for variant in VARIANTS:
            assert task["oracle"][variant] == want


def test_rule_both_variants_pass():
    cells = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in VARIANTS:
                loop = _run(tmp, task, variant, lambda _p, t=task, v=variant: json.dumps(rule_agent(t, v), ensure_ascii=False))
                cell = _score(task, variant, loop)
                cells.append(cell)
                assert loop["contract_error"] == "ok"
                assert loop["coordinator_exec_denied"] is True
                assert loop["env_denied"] is True
                assert cell["measurement_valid"] is True
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])
    summary = metrics(cells)
    assert summary["pass_gate"]["holds"] is True, summary
    assert summary["rates"]["StrictPair"] == 1.0


def test_skip_to_third_fails():
    task = load_tasks()[0]
    want = want_resume(task)
    payload = {
        "completed_steps": want["completed_steps"],
        "resume_step": task["step_ids"][2],
        "remaining_steps": [task["step_ids"][2]],
    }
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "control", lambda _p: json.dumps(payload))
        cell = _score(task, "control", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "resume_from_wrong_step"


def test_repeat_completed_fails():
    task = load_tasks()[1]
    payload = {
        "completed_steps": [task["step_ids"][0]],
        "resume_step": task["step_ids"][0],
        "remaining_steps": list(task["step_ids"]),
    }
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps(payload))
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "completed_step_repeated"


def test_remaining_skips_middle():
    task = load_tasks()[2]
    want = want_resume(task)
    payload = {
        "completed_steps": want["completed_steps"],
        "resume_step": want["resume_step"],
        "remaining_steps": [task["step_ids"][2]],
    }
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "control", lambda _p: json.dumps(payload))
        cell = _score(task, "control", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "remaining_step_skipped"


def test_empty_contract_rejected():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(Path(raw), task, "control", lambda _p: "")
        cell = _score(task, "control", loop)
        assert loop["contract_error"] == "empty"
        assert cell["measurement_valid"] is True
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "empty"


def test_control_prompt_no_interrupt_and_no_noisy_keys():
    for task in load_tasks():
        control = agent_prompt(task, "control")
        intervention = agent_prompt(task, "intervention")
        token = str(task["interrupt_token"])
        assert token not in control
        assert token in intervention
        noisy = checkpoint_for(task, "intervention")
        for key in noisy["outputs"]:
            assert key not in json.dumps(checkpoint_for(task, "control")["outputs"])
            if key != task["step_ids"][0]:
                assert f'"{key}"' not in control or key in json.dumps(task["step_ids"])


def test_intervention_checkpoint_has_future_keys():
    for task in load_tasks():
        ck = checkpoint_for(task, "intervention")
        assert ck["completed_steps"] == [task["step_ids"][0]]
        assert task["step_ids"][0] not in ck["outputs"]
        assert task["step_ids"][1] in ck["outputs"]
        assert task["step_ids"][2] in ck["outputs"]


def main() -> int:
    test_new_tasks_not_l1()
    print("new resume tasks, not L1 items")
    test_oracle_matches_platform_next_step()
    print("oracle uses platform next_step")
    test_rule_both_variants_pass()
    print("rule both variants pass")
    test_skip_to_third_fails()
    print("skip to third: fail-as-expected")
    test_repeat_completed_fails()
    print("repeat completed: fail-as-expected")
    test_remaining_skips_middle()
    print("remaining skip: fail-as-expected")
    test_empty_contract_rejected()
    print("empty contract: reject")
    test_control_prompt_no_interrupt_and_no_noisy_keys()
    print("control prompt isolation")
    test_intervention_checkpoint_has_future_keys()
    print("intervention has future output keys")
    print("CAL-GM-L1-RESUME-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
