#!/usr/bin/env python3
"""Rule calibration for EXP-GM-OA-01. Must pass before GLM."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_oa_01.channel import ChangeGateChannel, ENV_REWRITE
from exp_gm_oa_01.loader import load_tasks
from exp_gm_oa_01.loop import run_cell_loop
from exp_gm_oa_01.prompts import rule_agent, rule_decision
from exp_gm_oa_01.scorer import score_cell

PROTOCOLS = ("legacy_direct", "need_change_gate")
VARIANTS = ("control", "intervention")


def _run(tmp: Path, task: dict, variant: str, protocol: str, agent_fn):
    return run_cell_loop(
        task=task,
        variant=variant,
        protocol=protocol,
        task_id=f"{task['id']}_{variant}_{protocol}_rule",
        out_dir=tmp / f"{task['id']}_{variant}_{protocol}",
        agent_fn=agent_fn,
    )


def _score(task: dict, variant: str, protocol: str, loop: dict) -> dict:
    return score_cell(
        task=task,
        variant=variant,
        protocol=protocol,
        seed=0,
        loop=loop,
        workflow_id="rule",
        instance_id=loop["task_id"],
    )


def test_oracle_matches_rule():
    for task in load_tasks():
        for variant in VARIANTS:
            notice = {
                "event_id": f"event-{task['id']}-{variant}",
                "current_state": __import__("exp_gm_oa_01.loader", fromlist=["current_state"]).current_state(task, variant),
            }
            decided = rule_decision(task, notice)
            oracle = task["oracle"][variant]
            assert decided["need_change"] == oracle["need_change"], (task["id"], variant, decided, oracle)
            assert decided["action"] == oracle["action"]
            assert str(decided["target"]) == str(oracle["target"])
            assert decided["value"] == oracle["value"] or str(decided["value"]) == str(oracle["value"])


def test_control_keep_and_intervention_revise():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for protocol in PROTOCOLS:
                for variant in VARIANTS:
                    loop = _run(tmp, task, variant, protocol, lambda notice, plan: rule_agent(task, protocol, notice))
                    cell = _score(task, variant, protocol, loop)
                    assert cell["measurement_valid"] is True, (task["id"], protocol, variant, cell)
                    assert cell["full_pass"] == 1, (
                        task["id"],
                        protocol,
                        variant,
                        cell["process_profile"]["first_error"],
                        cell.get("extra"),
                    )


def test_control_unauthorized_revise_fails():
    task = next(item for item in load_tasks() if item["id"] == "resource_threshold")
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        def agent(notice, _plan):
            return {
                "need_change": True,
                "action": "revise",
                "target": "purchase_qty",
                "value": 1,
                "evidence_event_id": notice["event_id"],
            }

        for protocol in PROTOCOLS:
            loop = _run(tmp, task, "control", protocol, agent)
            cell = _score(task, "control", protocol, loop)
            assert cell["measurement_valid"] is True
            assert cell["full_pass"] == 0
            assert cell["process_profile"]["first_error"] == "control_false_positive_change"


def test_intervention_keep_fails():
    task = next(item for item in load_tasks() if item["id"] == "resource_threshold")
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        def agent(notice, _plan):
            return {
                "need_change": False,
                "action": "keep",
                "target": "NONE",
                "value": "NONE",
                "evidence_event_id": notice["event_id"],
            }

        for protocol in PROTOCOLS:
            loop = _run(tmp, task, "intervention", protocol, agent)
            cell = _score(task, "intervention", protocol, loop)
            assert cell["full_pass"] == 0
            assert cell["process_profile"]["first_error"] == "intervention_missed_change"


def test_need_change_false_with_revision_fails():
    task = next(item for item in load_tasks() if item["id"] == "resource_threshold")
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        def agent(notice, _plan):
            return {
                "need_change": False,
                "action": "keep",
                "target": "purchase_qty",
                "value": 1,
                "evidence_event_id": notice["event_id"],
            }

        loop = _run(tmp, task, "control", "need_change_gate", agent)
        cell = _score(task, "control", "need_change_gate", loop)
        assert cell["full_pass"] == 0
        assert cell["extra"]["need_change_correct"] is True
        assert cell["process_profile"]["first_error"] == "keep_placeholder_not_none"

        def revise_against_flag(notice, _plan):
            return {
                "need_change": False,
                "action": "revise",
                "target": "purchase_qty",
                "value": 1,
                "evidence_event_id": notice["event_id"],
            }

        loop2 = _run(tmp / "b", task, "control", "need_change_gate", revise_against_flag)
        cell2 = _score(task, "control", "need_change_gate", loop2)
        assert cell2["full_pass"] == 0
        assert cell2["process_profile"]["first_error"] == "need_change_action_inconsistent"

        assert cell2["extra"]["need_change_correct"] is False


def test_environment_cannot_rewrite_plan():
    with tempfile.TemporaryDirectory() as raw:
        channel = ChangeGateChannel(Path(raw) / "c.jsonl")
        channel.register_plan("t", {"purchase_qty": 0, "stock": 6})
        denied = channel.rewrite_plan("t", role="environment", target="purchase_qty", value=1)
        assert denied["ok"] is False
        assert denied["reason"] == ENV_REWRITE
        assert channel.plan["purchase_qty"] == 0
        task = next(item for item in load_tasks() if item["id"] == "resource_threshold")
        loop = _run(
            Path(raw),
            task,
            "control",
            "need_change_gate",
            lambda notice, plan: rule_agent(task, "need_change_gate", notice),
        )
        loop["channel"].rewrite_plan(loop["task_id"], role="environment", target="purchase_qty", value=1)
        loop["env_rewrote"] = True
        loop["source_contamination"] = True
        cell = _score(task, "control", "need_change_gate", loop)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "environment_rewrote_plan"
        assert cell["process_profile"]["source_contamination"] is True


def main() -> int:
    test_oracle_matches_rule()
    print("oracle alignment: pass")
    test_control_keep_and_intervention_revise()
    print("rule keep/revise: pass")
    test_control_unauthorized_revise_fails()
    print("control unauthorized revise: fail-as-expected")
    test_intervention_keep_fails()
    print("intervention keep: fail-as-expected")
    test_need_change_false_with_revision_fails()
    print("need_change contradiction: fail-as-expected")
    test_environment_cannot_rewrite_plan()
    print("environment rewrite: fail-as-expected + source contamination")
    print("EXP-GM-OA-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
