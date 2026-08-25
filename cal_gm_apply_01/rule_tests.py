#!/usr/bin/env python3
"""Rule calibration for CAL-GM-APPLY-01. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cal_gm_apply_01.loader import load_tasks, required_changes
from cal_gm_apply_01.loop import run_cell
from cal_gm_apply_01.prompts import executor_prompt, rule_executor
from cal_gm_apply_01.scorer import metrics, score_cell

VARIANTS = ("control", "intervention")


def _run(tmp: Path, task: dict, variant: str, executor_fn):
    return run_cell(
        task=task,
        variant=variant,
        instance_id=f"{task['id']}_{variant}_rule",
        out_dir=tmp / f"{task['id']}_{variant}",
        executor_fn=executor_fn,
    )


def _score(task: dict, variant: str, loop: dict) -> dict:
    return score_cell(
        task=task,
        variant=variant,
        repeat_id=0,
        loop=loop,
        workflow_id="cal_gm_apply_01_rule",
        instance_id=loop["instance_id"],
    )


def test_rule_applies_complete():
    cells = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in VARIANTS:
                loop = _run(tmp, task, variant, lambda _p, t=task, v=variant: rule_executor(t, v, t["draft"]))
                cell = _score(task, variant, loop)
                cells.append(cell)
                extra = cell.get("extra") or {}
                assert cell["measurement_valid"] is True, (task["id"], variant)
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])
                assert extra["complete"] is True
                assert extra["partial"] is False
                assert extra["hidden_test_pass"] is True
                assert extra["acknowledgement_execution_gap"] is False
                source = Path(loop["final_path"]).read_text(encoding="utf-8")
                for change in required_changes(task, variant):
                    assert f"{change['path']} = {change['new_value']}" in source
                if variant == "control":
                    assert f"{task['secondary']} = {task['current']}" in source
    summary = metrics(cells)
    assert summary["pass_gate"]["holds"] is True, summary


def test_partial_change_caught():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        def executor(_prompt: str) -> str:
            return rule_executor(task, "control", task["draft"])

        loop = _run(Path(raw), task, "intervention", executor)
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        assert cell["extra"]["partial"] is True
        assert cell["process_profile"]["first_error"] == "partial_change_applied"


def test_unregistered_change_caught():
    task = load_tasks()[1]
    with tempfile.TemporaryDirectory() as raw:
        def executor(_prompt: str) -> str:
            return rule_executor(task, "control", task["draft"]) + "EXTRA_FLAG = 1\n"

        loop = _run(Path(raw), task, "control", executor)
        cell = _score(task, "control", loop)
        assert cell["full_pass"] == 0
        assert cell["extra"]["unregistered"] is True
        assert cell["process_profile"]["first_error"] == "unregistered_change"


def test_ack_without_apply_caught():
    task = load_tasks()[2]
    with tempfile.TemporaryDirectory() as raw:
        def executor(_prompt: str) -> str:
            return task["draft"] + 'APPLIED_PATCH_IDS = ["patch-01"]\n'

        loop = _run(Path(raw), task, "control", executor)
        cell = _score(task, "control", loop)
        assert cell["full_pass"] == 0
        assert cell["extra"]["acknowledgement_execution_gap"] is True
        assert cell["process_profile"]["first_error"] == "change_acknowledged_not_applied"
        assert f"{task['primary']} = {task['current']}" in Path(loop["final_path"]).read_text(encoding="utf-8")


def test_environment_does_not_rewrite():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        def executor(_prompt: str) -> str:
            return task["draft"]

        loop = _run(Path(raw), task, "intervention", executor)
        disk = Path(loop["final_path"]).read_text(encoding="utf-8")
        assert disk == task["draft"]
        assert f"{task['primary']} = {task['required']}" not in disk
        assert loop["environment_rewrote"] is False
        cell = _score(task, "intervention", loop)
        assert cell["process_profile"]["first_error"] == "required_change_not_read"


def test_control_review_omits_secondary():
    for task in load_tasks():
        prompt = executor_prompt(task, "control", task["draft"])
        payload = json.loads(prompt.split("【修改要求】", 1)[1].split("\n", 1)[0])
        paths = [item["path"] for item in payload["required_changes"]]
        assert paths == [task["primary"]], (task["id"], paths)
        assert task["secondary"] in task["draft"]


def test_scorer_reads_disk_not_claim():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        loop = _run(tmp, task, "control", lambda _p: rule_executor(task, "control", task["draft"]))
        Path(loop["final_path"]).write_text(task["draft"], encoding="utf-8")
        cell = _score(task, "control", loop)
        assert cell["full_pass"] == 0
        assert cell["extra"]["complete"] is False
        assert cell["extra"]["got"][task["primary"]] == task["current"]


def main() -> int:
    test_rule_applies_complete()
    print("rule complete adoption: pass")
    test_partial_change_caught()
    print("partial change: fail-as-expected")
    test_unregistered_change_caught()
    print("unregistered change: fail-as-expected")
    test_ack_without_apply_caught()
    print("ack without apply: fail-as-expected")
    test_environment_does_not_rewrite()
    print("environment rewrite: denied")
    test_control_review_omits_secondary()
    print("control review omits secondary path")
    test_scorer_reads_disk_not_claim()
    print("scorer rereads file, ignores in-memory success")
    print("CAL-GM-APPLY-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
