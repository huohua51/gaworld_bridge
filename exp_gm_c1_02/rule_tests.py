#!/usr/bin/env python3
"""Rule calibration for EXP-GM-C1-02. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from exp_gm_c1_02.channel import CoordinationChannel
from exp_gm_c1_02.loader import BANNED, leak_tokens_for, load_tasks, oracle_plan, solve
from exp_gm_c1_02.loop import run_cell, run_direct
from exp_gm_c1_02.prompts import rule_commit, rule_direct, rule_plan_from_reports, rule_report, rule_revision
from exp_gm_c1_02.scorer import score_cell


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _parse_after(prompt: str, marker: str) -> dict:
    if marker not in prompt:
        return {}
    raw = prompt.split(marker, 1)[1].split("\n", 1)[0].strip()
    return json.loads(raw)


def _run(tmp: Path, task: dict, variant: str, track: str, **overrides):
    def report_a(_p):
        return _dump(rule_report(task, "agent_a", baseline=True))

    def report_b(_p):
        return _dump(rule_report(task, "agent_b", baseline=True))

    def initial_fn(prompt: str):
        reports = _parse_after(prompt, "【已送达初始报告】")
        return _dump(rule_plan_from_reports(task, reports, version="plan-init"))

    def revision_fn(_p):
        return _dump(rule_revision(task, variant))

    def propose_fn(prompt: str):
        latest = _parse_after(prompt, "【最新已送达约束】")
        return _dump(rule_plan_from_reports(task, latest, version="plan-001"))

    def commit_a(prompt: str):
        plan = json.loads(prompt.split("【联合方案】", 1)[1].strip()) if "【联合方案】" in prompt else None
        return _dump(rule_commit(task, "agent_a", variant, plan))

    def commit_b(prompt: str):
        plan = json.loads(prompt.split("【联合方案】", 1)[1].strip()) if "【联合方案】" in prompt else None
        return _dump(rule_commit(task, "agent_b", variant, plan))

    loop = run_cell(
        task=task,
        variant=variant,
        track=track,
        out_dir=tmp / f"{task['id']}_{variant}_{track}",
        report_a_fn=overrides.get("report_a_fn", report_a),
        report_b_fn=overrides.get("report_b_fn", report_b),
        initial_fn=overrides.get("initial_fn", initial_fn),
        revision_fn=overrides.get("revision_fn", revision_fn),
        propose_fn=overrides.get("propose_fn", propose_fn),
        commit_a_fn=overrides.get("commit_a_fn", commit_a),
        commit_b_fn=overrides.get("commit_b_fn", commit_b),
    )
    cell = score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=0,
        loop=loop,
        workflow_id="exp_gm_c1_02_rule",
        instance_id=f"{task['id']}_{variant}_{track}",
    )
    return cell, loop


def test_not_old_items():
    ids = {task["id"] for task in load_tasks()}
    assert ids == {"c1_02_optics_table_001", "c1_02_greenhouse_001", "c1_02_cold_store_001"}
    for task in load_tasks():
        blob = json.dumps(task, default=str)
        for token in BANNED:
            assert token not in blob, token


def test_oracle_unique():
    for task in load_tasks():
        for variant in ("control", "intervention"):
            got = solve(task, variant)
            want = task["oracle"][variant]["assignments"]
            assert got == want, (task["id"], variant, got, want)
            assert oracle_plan(task, variant)["initial_conflict"] == (variant == "intervention")
            assert oracle_plan(task, variant)["initial_conflict"] == task["oracle"][variant]["initial_conflict"]


def test_direct_rule():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in ("control", "intervention"):
                loop = run_direct(task=task, variant=variant, out_dir=tmp / f"{task['id']}_{variant}_direct", generate_fn=lambda _p, t=task, v=variant: _dump(rule_direct(t, v)))
                cell = score_cell(task=task, variant=variant, track="direct", repeat_id=0, loop=loop, workflow_id="c102_direct", instance_id=f"{task['id']}_{variant}_direct")
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])


def test_rule_tracks():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in ("control", "intervention"):
                cell, loop = _run(tmp, task, variant, "multi")
                assert cell["measurement_valid"], (task["id"], variant, cell)
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])
                assert loop["budget"]["calls"] == 7
                assert loop["coordinator_exec_denied"] is True
                if variant == "intervention":
                    assert loop["violations"]
                    assert loop["violations"][0]["type"] == "duplicate_resource_claim"
                    repair = task["oracle"]["intervention"]["assignments"]["agent_b"]
                    assert repair not in json.dumps(loop["violations"])
            drop_c, drop_c_loop = _run(tmp, task, "control", "drop_revision")
            assert drop_c["full_pass"] == 1, (task["id"], drop_c["process_profile"])
            drop_i, drop_i_loop = _run(tmp, task, "intervention", "drop_revision")
            assert drop_i["measurement_valid"]
            assert drop_i["full_pass"] == 0
            assert drop_i["process_profile"]["first_error"] == "constraint_revision_not_delivered"
            assert drop_i_loop["b_ran"] is True
            assert drop_i_loop["revision_delivered"] is False
            assert "agent_b" in (drop_i_loop["latest"] or {}) or "agent_b" in (drop_i_loop.get("reports") or {})
            for variant in ("control", "intervention"):
                dc, dc_loop = _run(tmp, task, variant, "drop_coordinator")
                assert dc["measurement_valid"]
                assert dc["full_pass"] == 0
                assert dc["process_profile"]["first_error"] == "plan_not_delivered"
                assert dc_loop["coordinator_ran"] is True
                assert dc_loop["plan_delivered"] is False


def test_privacy_and_env():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        channel = CoordinationChannel(tmp / "c.jsonl")
        channel.put_private("agent_b", {"secret": "b_rev_optics_v2"})
        assert channel.read_private("agent_a", "agent_b")["reason"] == "unauthorized_private_read"
        assert channel.read_private("coordinator", "agent_b")["reason"] == "unauthorized_private_read"
        assert channel.submit_claim(role="coordinator", agent_id="agent_a", slot="w08", plan_version="plan-001")["ok"] is False
        _, loop = _run(tmp, task, "intervention", "multi")
        for token in leak_tokens_for(task, "intervention"):
            assert token not in loop["prompts"]["agent_a_report"]
            assert token in loop["prompts"]["agent_b_revision"]
            assert token not in loop["prompts"]["coordinator_initial"]
        text = Path(loop["world_path"]).read_text(encoding="utf-8")
        assert "ENVIRONMENT_REWRITE" not in text
        assert loop["env_denied"] is True


def test_deviations():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        def bad_plan(_p):
            return _dump({"plan_version": "plan-001", "assignments": {"agent_a": "w08", "agent_b": "w08"}, "rule": "priority_keep_then_earliest_free"})

        cell, _ = _run(tmp, task, "intervention", "multi", propose_fn=bad_plan)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] in {"joint_plan_not_revised", "invalid_joint_assignment", "final_state_conflict"}

        def deviate(_p):
            return _dump({"agent_id": "agent_b", "plan_version": "plan-001", "confirm": True, "slot": "w10"})

        cell, _ = _run(tmp, task, "control", "multi", commit_b_fn=deviate)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "execution_deviated_from_plan"


def test_fairness():
    from exp_gm_c1_02.fairness import preflight

    check = preflight()
    assert check["ok"], check["leaks"]


def main() -> int:
    test_not_old_items()
    print("new C1-02 tasks, not C1-01/COMP/REPAIR items")
    test_oracle_unique()
    print("Oracle unique")
    test_direct_rule()
    print("Rule Direct pass")
    test_rule_tracks()
    print("Multi both variants pass; Drop revision control pass / intervention fail; Drop coordinator plan_not_delivered")
    test_privacy_and_env()
    print("privacy, coordinator cannot execute, env rewrite denied")
    test_deviations()
    print("bad plan / execution deviate caught")
    test_fairness()
    print("fairness pass")
    print("EXP-GM-C1-02 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
