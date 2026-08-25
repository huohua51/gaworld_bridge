#!/usr/bin/env python3
"""Rule calibration for CAL-GM-CHANGE-01. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cal_gm_change_01.contract import CONTRACT_KEEP_EXTRA, CONTRACT_UPDATE_MISSING, KEEP, UPDATE
from cal_gm_change_01.loader import load_tasks, required_value
from cal_gm_change_01.loop import run_cell
from cal_gm_change_01.prompts import agent_prompt, rule_agent
from cal_gm_change_01.scorer import metrics, score_cell

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
        workflow_id="cal_gm_change_01_rule",
        instance_id=loop["instance_id"],
    )


def test_rule_keep_and_update_pass():
    cells = []
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in VARIANTS:
                loop = _run(tmp, task, variant, lambda _p, t=task, v=variant: json.dumps(rule_agent(t, v), ensure_ascii=False))
                cell = _score(task, variant, loop)
                cells.append(cell)
                assert loop["contract_error"] == "ok", (task["id"], variant, loop["contract_error"])
                assert cell["measurement_valid"] is True
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])
                if variant == "control":
                    assert loop["action"]["decision"] == KEEP
                    assert loop["action"]["required_change"] is None
                else:
                    assert loop["action"]["decision"] == UPDATE
                    change = loop["action"]["required_change"]
                    assert change["path"] == task["path"]
                    assert change["old_value"] == task["current"]
                    assert change["new_value"] == required_value(task, variant)
    summary = metrics(cells)
    assert summary["pass_gate"]["holds"] is True, summary
    assert summary["rates"]["FalsePositiveRevisionRate"] == 0.0
    assert summary["rates"]["MissedRevisionRate"] == 0.0
    assert summary["rates"]["StrictPair"] == 1.0


def test_control_update_fails():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        payload = {
            "decision": UPDATE,
            "evidence": {"path": task["path"], "observed": task["current"], "required": task["control_required"]},
            "required_change": {"path": task["path"], "old_value": task["current"], "new_value": task["intervention_required"]},
        }
        loop = _run(Path(raw), task, "control", lambda _p: json.dumps(payload))
        cell = _score(task, "control", loop)
        assert loop["contract_error"] == "ok"
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "false_positive_revision"
        assert cell["extra"]["false_positive_revision"] is True


def test_intervention_keep_fails():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        payload = {
            "decision": KEEP,
            "evidence": {"path": task["path"], "observed": task["current"], "required": task["intervention_required"]},
            "required_change": None,
        }
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps(payload))
        cell = _score(task, "intervention", loop)
        assert loop["contract_error"] == "ok"
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "missed_revision"


def test_keep_with_required_change_rejected():
    task = load_tasks()[1]
    with tempfile.TemporaryDirectory() as raw:
        payload = {
            "decision": KEEP,
            "evidence": {"path": task["path"], "observed": task["current"], "required": task["control_required"]},
            "required_change": {"path": task["path"], "old_value": task["current"], "new_value": task["current"]},
        }
        loop = _run(Path(raw), task, "control", lambda _p: json.dumps(payload))
        cell = _score(task, "control", loop)
        assert loop["contract_error"] == CONTRACT_KEEP_EXTRA
        assert cell["measurement_valid"] is True
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == CONTRACT_KEEP_EXTRA


def test_update_missing_fields_rejected():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        payload = {
            "decision": UPDATE,
            "evidence": {"path": task["path"], "observed": task["current"], "required": task["intervention_required"]},
            "required_change": None,
        }
        loop = _run(Path(raw), task, "intervention", lambda _p: json.dumps(payload))
        cell = _score(task, "intervention", loop)
        assert loop["contract_error"] == CONTRACT_UPDATE_MISSING
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == CONTRACT_UPDATE_MISSING


def test_wrong_evidence_not_grounded():
    task = load_tasks()[2]
    with tempfile.TemporaryDirectory() as raw:
        payload = {
            "decision": KEEP,
            "evidence": {"path": task["path"], "observed": 99, "required": task["control_required"]},
            "required_change": None,
        }
        loop = _run(Path(raw), task, "control", lambda _p: json.dumps(payload))
        cell = _score(task, "control", loop)
        assert loop["contract_error"] == "ok"
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "evidence_not_grounded"


def test_control_prompt_does_not_leak_intervention():
    for task in load_tasks():
        prompt = agent_prompt(task, "control")
        token = str(task["intervention_required"])
        assert token not in prompt, (task["id"], token, prompt)


def test_environment_cannot_rewrite_action():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        loop = _run(
            Path(raw),
            task,
            "control",
            lambda _p: json.dumps(rule_agent(task, "control"), ensure_ascii=False),
        )
        assert loop["action"]["decision"] == KEEP
        # The harness never rewrites Agent output; Scorer reads the emitted action only.
        rewritten = dict(loop["action"])
        rewritten["decision"] = UPDATE
        assert loop["action"]["decision"] == KEEP
        assert rewritten["decision"] != loop["action"]["decision"]


def main() -> int:
    test_rule_keep_and_update_pass()
    print("rule keep/update: pass")
    test_control_update_fails()
    print("control update: fail-as-expected")
    test_intervention_keep_fails()
    print("intervention keep: fail-as-expected")
    test_keep_with_required_change_rejected()
    print("keep carries required_change: contract reject")
    test_update_missing_fields_rejected()
    print("update missing fields: contract reject")
    test_wrong_evidence_not_grounded()
    print("wrong evidence: not grounded")
    test_control_prompt_does_not_leak_intervention()
    print("control prompt does not leak intervention value")
    test_environment_cannot_rewrite_action()
    print("environment rewrite: denied")
    print("CAL-GM-CHANGE-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
