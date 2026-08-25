#!/usr/bin/env python3
"""Rule calibration for EXP-GM-C1-01. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from exp_gm_c1_01.channel import CoordinationChannel
from exp_gm_c1_01.loader import leak_tokens_for, load_tasks, oracle_plan, solve
from exp_gm_c1_01.loop import run_cell, run_direct
from exp_gm_c1_01.prompts import rule_commit, rule_direct, rule_plan, rule_report
from exp_gm_c1_01.scorer import score_cell


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _run(tmp: Path, task: dict, variant: str, track: str, **overrides):
    def report_a(_p):
        return _dump(rule_report(task, "agent_a", variant))

    def report_b(_p):
        return _dump(rule_report(task, "agent_b", variant))

    def plan_fn(prompt: str):
        marker = "【已送达约束报告】"
        reports = {}
        if marker in prompt:
            raw = prompt.split(marker, 1)[1].split("\n", 1)[0].strip()
            reports = json.loads(raw)
        return _dump(rule_plan(task, variant, reports, global_view=track == "single"))

    def commit_a(prompt: str):
        plan = None
        marker = "【联合方案】"
        if marker in prompt:
            plan = json.loads(prompt.split(marker, 1)[1].strip())
        return _dump(rule_commit(task, "agent_a", variant, plan))

    def commit_b(prompt: str):
        plan = None
        marker = "【联合方案】"
        if marker in prompt:
            plan = json.loads(prompt.split(marker, 1)[1].strip())
        return _dump(rule_commit(task, "agent_b", variant, plan))

    loop = run_cell(
        task=task,
        variant=variant,
        track=track,
        out_dir=tmp / f"{task['id']}_{variant}_{track}",
        report_a_fn=overrides.get("report_a_fn", report_a),
        report_b_fn=overrides.get("report_b_fn", report_b),
        plan_fn=overrides.get("plan_fn", plan_fn),
        commit_a_fn=overrides.get("commit_a_fn", commit_a),
        commit_b_fn=overrides.get("commit_b_fn", commit_b),
    )
    cell = score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=0,
        loop=loop,
        workflow_id="exp_gm_c1_01_rule",
        instance_id=f"{task['id']}_{variant}_{track}",
    )
    return cell, loop


def test_oracle_unique():
    for task in load_tasks():
        for variant in ("control", "intervention"):
            got = solve(task, variant)
            want = task["oracle"][variant]["assignments"]
            assert got == want, (task["id"], variant, got, want)
            assert oracle_plan(task, variant)["conflict"] == task["oracle"][variant]["conflict"]
            assert oracle_plan(task, variant)["conflict"] == (variant == "intervention")


def test_rule_tracks():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in ("control", "intervention"):
                for track in ("single", "multi"):
                    cell, loop = _run(tmp, task, variant, track)
                    assert cell["measurement_valid"], (task["id"], variant, track, cell)
                    assert cell["full_pass"] == 1, (task["id"], variant, track, cell["process_profile"])
                    assert loop["budget"]["calls"] == 5
                    assert loop["budget"]["kinds"] == [
                        "agent_a_report",
                        "agent_b_report",
                        "coordinator_plan",
                        "agent_a_commit",
                        "agent_b_commit",
                    ]
                drop, drop_loop = _run(tmp, task, variant, "drop")
                assert drop["measurement_valid"], (task["id"], variant, drop)
                assert drop["full_pass"] == 0
                assert drop["process_profile"]["first_error"] == "constraint_message_not_delivered"
                assert drop_loop["b_ran"] is True
                assert drop_loop["b_delivered"] is False
                assert drop_loop["coordinator_ran"] is True


def test_direct_rule():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in ("control", "intervention"):
                loop = run_direct(task=task, variant=variant, out_dir=tmp / f"{task['id']}_{variant}_direct", generate_fn=lambda _p, t=task, v=variant: _dump(rule_direct(t, v)))
                cell = score_cell(task=task, variant=variant, track="direct", repeat_id=0, loop=loop, workflow_id="c1_direct_rule", instance_id=f"{task['id']}_{variant}_direct")
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])


def test_drop_and_privacy():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        channel = CoordinationChannel(tmp / "c.jsonl")
        channel.put_private("agent_b", {"secret": "b_window_v2"})
        denied = channel.read_private("agent_a", "agent_b")
        assert denied["reason"] == "unauthorized_private_read"
        coord = channel.read_private("coordinator", "agent_b")
        assert coord["reason"] == "unauthorized_private_read"
        env = channel.submit_claim(role="environment", agent_id="agent_a", slot="09:00", plan_version="plan-001")
        assert env["ok"] is False
        _, loop = _run(tmp, task, "intervention", "multi")
        for token in leak_tokens_for(task, "intervention"):
            assert token not in loop["prompts"]["agent_a_report"]
            assert token in loop["prompts"]["agent_b_report"]


def test_conflict_not_detected():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        want = oracle_plan(task, "intervention")

        def plan_fn(_p):
            return _dump({**want, "conflict": False})

        cell, _ = _run(tmp, task, "intervention", "multi", plan_fn=plan_fn)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "conflict_not_detected"


def test_invalid_and_deviations():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        def bad_plan(_p):
            return _dump({"plan_version": "plan-001", "conflict": True, "assignments": {"agent_a": "09:00", "agent_b": "09:00"}, "rule": "priority_keep_then_earliest_free"})

        cell, _ = _run(tmp, task, "intervention", "multi", plan_fn=bad_plan)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] in {"invalid_joint_plan", "duplicate_resource_claim"}

        def deviate(prompt: str):
            return _dump({"agent_id": "agent_b", "plan_version": "plan-001", "confirm": True, "slot": "11:00"})

        cell, _ = _run(tmp, task, "control", "multi", commit_b_fn=deviate)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "execution_deviated_from_plan"

        def reject(prompt: str):
            return _dump({"agent_id": "agent_a", "plan_version": "plan-001", "confirm": False, "slot": None})

        cell, _ = _run(tmp, task, "control", "single", commit_a_fn=reject)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "agent_rejected_assignment"


def test_environment_rewrite_denied():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        _, loop = _run(tmp, task, "control", "multi")
        text = Path(loop["world_path"]).read_text(encoding="utf-8")
        assert "ENVIRONMENT_REWRITE" not in text
        assert loop["env_denied"] is True


def test_fairness():
    from exp_gm_c1_01.fairness import preflight

    check = preflight()
    assert check["ok"], check["leaks"]


def test_not_t3_items():
    ids = {task["id"] for task in load_tasks()}
    assert ids == {"c1_charge_slot_001", "c1_device_book_001", "c1_dock_window_001"}
    banned = ("parking", "FREE_SHIP_KG", "REDEEM_MIN", "ALERT_C", "n1_bridge")
    for task in load_tasks():
        blob = str(task)
        for token in banned:
            assert token not in blob


def main() -> int:
    test_not_t3_items()
    print("new C1 tasks, not T3/N1 items")
    test_oracle_unique()
    print("Oracle unique assignments match the registered rule")
    test_direct_rule()
    print("Rule Direct control+intervention pass")
    test_rule_tracks()
    print("Rule Single/Multi both variants pass; Drop fails constraint_message_not_delivered")
    test_drop_and_privacy()
    print("peer/coordinator cannot read private; Drop sender runs")
    test_conflict_not_detected()
    print("forced conflict=false: conflict_not_detected")
    test_invalid_and_deviations()
    print("duplicate/invalid plan, execution deviate, reject assignment caught")
    test_environment_rewrite_denied()
    print("environment rewrite denied")
    test_fairness()
    print("fairness prompts: pass")
    print("EXP-GM-C1-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
