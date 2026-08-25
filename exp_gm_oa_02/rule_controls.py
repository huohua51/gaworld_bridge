#!/usr/bin/env python3
"""Rule calibration for EXP-GM-OA-02. Must pass before GLM. OA-01 scorer is not used."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_oa_01.loader import load_tasks
from exp_gm_oa_02.channel import ExclusiveActionChannel, ENV_REWRITE
from exp_gm_oa_02.contract import CONTRACT_KEEP_EXTRA, CONTRACT_REVISE_MISSING, KEEP, REVISE
from exp_gm_oa_02.loop import run_cell_loop
from exp_gm_oa_02.prompts import rule_agent
from exp_gm_oa_02.scorer import score_cell

VARIANTS = ("control", "intervention")


def _run(tmp: Path, task: dict, variant: str, agent_fn):
    return run_cell_loop(
        task=task,
        variant=variant,
        instance_id=f"{task['id']}_{variant}_rule",
        out_dir=tmp / f"{task['id']}_{variant}",
        agent_fn=agent_fn,
    )


def _score(task: dict, variant: str, loop: dict) -> dict:
    return score_cell(
        task=task,
        variant=variant,
        seed=0,
        loop=loop,
        workflow_id="rule",
        instance_id=loop["task_id"],
    )


def test_rule_keep_and_revise_pass():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in VARIANTS:
                loop = _run(tmp, task, variant, lambda notice, plan: rule_agent(task, notice))
                cell = _score(task, variant, loop)
                assert cell["measurement_valid"] is True, (task["id"], variant, cell)
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"]["first_error"], cell.get("extra"))
                assert loop["contract_error"] == "ok"
                if variant == "control":
                    assert loop["action"]["action"] == KEEP
                    assert "target" not in loop["action"]
                    assert "value" not in loop["action"]
                else:
                    assert loop["action"]["action"] == REVISE
                    assert "target" in loop["action"] and "value" in loop["action"]


def test_control_revise_fails():
    task = next(item for item in load_tasks() if item["id"] == "resource_threshold")
    with tempfile.TemporaryDirectory() as raw:
        def agent(notice, _plan):
            return {
                "action": REVISE,
                "target": "purchase_qty",
                "value": 1,
                "evidence_event_id": notice["event_id"],
            }

        loop = _run(Path(raw), task, "control", agent)
        cell = _score(task, "control", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "control_false_positive_change"


def test_intervention_keep_fails():
    task = next(item for item in load_tasks() if item["id"] == "resource_threshold")
    with tempfile.TemporaryDirectory() as raw:
        def agent(notice, _plan):
            return {"action": KEEP, "evidence_event_id": notice["event_id"]}

        loop = _run(Path(raw), task, "intervention", agent)
        cell = _score(task, "intervention", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "intervention_missed_change"


def test_keep_with_target_value_rejected():
    task = next(item for item in load_tasks() if item["id"] == "responsibility_update")
    with tempfile.TemporaryDirectory() as raw:
        def agent(notice, _plan):
            return {
                "action": KEEP,
                "target": "assignee_id",
                "value": "NONE",
                "evidence_event_id": notice["event_id"],
            }

        loop = _run(Path(raw), task, "control", agent)
        cell = _score(task, "control", loop)
        assert loop["contract_error"] == CONTRACT_KEEP_EXTRA
        assert loop["contract_rejected"] is True
        assert cell["measurement_valid"] is True
        assert cell["full_pass"] == 0
        assert cell["extra"]["contract_rejected"] is True
        assert cell["process_profile"]["first_error"] == CONTRACT_KEEP_EXTRA


def test_revise_missing_fields_rejected():
    task = next(item for item in load_tasks() if item["id"] == "resource_threshold")
    with tempfile.TemporaryDirectory() as raw:
        def agent(notice, _plan):
            return {"action": REVISE, "evidence_event_id": notice["event_id"]}

        loop = _run(Path(raw), task, "intervention", agent)
        cell = _score(task, "intervention", loop)
        assert loop["contract_error"] == CONTRACT_REVISE_MISSING
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == CONTRACT_REVISE_MISSING


def test_environment_cannot_rewrite():
    with tempfile.TemporaryDirectory() as raw:
        channel = ExclusiveActionChannel(Path(raw) / "c.jsonl")
        channel.register_plan("t", {"purchase_qty": 0})
        denied = channel.rewrite_plan("t", role="environment", target="purchase_qty", value=1)
        assert denied["reason"] == ENV_REWRITE
        assert channel.plan["purchase_qty"] == 0


def main() -> int:
    test_rule_keep_and_revise_pass()
    print("rule keep/revise: pass")
    test_control_revise_fails()
    print("control revise: fail-as-expected")
    test_intervention_keep_fails()
    print("intervention keep: fail-as-expected")
    test_keep_with_target_value_rejected()
    print("keep carries fields: contract reject")
    test_revise_missing_fields_rejected()
    print("revise missing fields: contract reject")
    test_environment_cannot_rewrite()
    print("environment rewrite: denied")
    print("EXP-GM-OA-02 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
