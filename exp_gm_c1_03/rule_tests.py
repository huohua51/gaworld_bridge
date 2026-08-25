#!/usr/bin/env python3
"""Rule calibration for EXP-GM-C1-03. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from exp_gm_c1_03.channel import CoordinationChannel
from exp_gm_c1_03.loader import BANNED, leak_tokens_for, load_tasks, oracle_plan, repair_slot_for, solve_final, solve_phase1
from exp_gm_c1_03.loop import run_cell, run_direct
from exp_gm_c1_03.prompts import rule_commit, rule_direct, rule_plan_from_reports, rule_report
from exp_gm_c1_03.scorer import score_cell


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _parse_after(prompt: str, marker: str) -> dict:
    if marker not in prompt:
        return {}
    raw = prompt.split(marker, 1)[1].split("\n", 1)[0].strip()
    return json.loads(raw)


def _fns(task: dict, variant: str):
    def report_a(_p):
        return _dump(rule_report(task, "agent_a", variant))

    def report_b(_p):
        return _dump(rule_report(task, "agent_b", variant))

    def initial_fn(prompt: str):
        reports = _parse_after(prompt, "【已送达初始报告】")
        return _dump(rule_plan_from_reports(task, reports, version="plan-init", variant=variant, stage="phase1"))

    def retry_fn(prompt: str):
        reports = _parse_after(prompt, "【已送达初始报告】")
        stage = "final" if "【登记保护修订】" in prompt else "phase1"
        return _dump(rule_plan_from_reports(task, reports, version="plan-001", variant=variant, stage=stage))

    def commit_a(prompt: str):
        plan = json.loads(prompt.split("【联合方案】", 1)[1].strip()) if "【联合方案】" in prompt else None
        return _dump(rule_commit(task, "agent_a", variant, plan))

    def commit_b(prompt: str):
        plan = json.loads(prompt.split("【联合方案】", 1)[1].strip()) if "【联合方案】" in prompt else None
        return _dump(rule_commit(task, "agent_b", variant, plan))

    return report_a, report_b, initial_fn, retry_fn, commit_a, commit_b


def _run(tmp: Path, task: dict, variant: str, track: str, **overrides):
    report_a, report_b, initial_fn, retry_fn, commit_a, commit_b = _fns(task, variant)
    loop = run_cell(
        task=task,
        variant=variant,
        track=track,
        out_dir=tmp / f"{task['id']}_{variant}_{track}",
        report_a_fn=overrides.get("report_a_fn", report_a),
        report_b_fn=overrides.get("report_b_fn", report_b),
        initial_fn=overrides.get("initial_fn", initial_fn),
        retry_fn=overrides.get("retry_fn", retry_fn),
        commit_a_fn=overrides.get("commit_a_fn", commit_a),
        commit_b_fn=overrides.get("commit_b_fn", commit_b),
    )
    cell = score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=0,
        loop=loop,
        workflow_id="exp_gm_c1_03_rule",
        instance_id=f"{task['id']}_{variant}_{track}",
    )
    return cell, loop


def test_not_old_items():
    ids = {task["id"] for task in load_tasks()}
    assert ids == {"c1_03_electrophoresis_001", "c1_03_cryostat_001", "c1_03_incubator_shelf_001"}
    for task in load_tasks():
        blob = json.dumps(task, default=str)
        for token in BANNED:
            assert token not in blob, token


def test_oracle_unique():
    for task in load_tasks():
        for variant in ("control", "intervention"):
            first = solve_phase1(task, variant)
            final = solve_final(task, variant)
            want = oracle_plan(task, variant)
            assert first == want["first"], (task["id"], variant, first, want["first"])
            assert final == want["assignments"], (task["id"], variant, final, want["assignments"])
            assert want["nack_expected"] == (variant == "intervention")
            if variant == "intervention":
                assert first != final
                assert first["agent_a"] != task["protection"]["slot"]


def test_direct_rule():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in ("control", "intervention"):
                loop = run_direct(
                    task=task,
                    variant=variant,
                    out_dir=tmp / f"{task['id']}_{variant}_direct",
                    generate_fn=lambda _p, t=task, v=variant: _dump(rule_direct(t, v)),
                )
                cell = score_cell(
                    task=task,
                    variant=variant,
                    track="direct",
                    repeat_id=0,
                    loop=loop,
                    workflow_id="c103_direct",
                    instance_id=f"{task['id']}_{variant}_direct",
                )
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])


def test_rule_tracks():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in ("control", "intervention"):
                cell, loop = _run(tmp, task, variant, "multi")
                assert cell["measurement_valid"], (task["id"], variant, cell)
                assert cell["full_pass"] == 1, (task["id"], variant, cell["process_profile"])
                assert loop["budget"]["calls"] == 6
                assert loop["coordinator_exec_denied"] is True
                assert loop["unregistered_modification"] == 0
                if variant == "intervention":
                    assert loop["nack_path"] is True
                    assert loop["violations"]
                    assert loop["violations"][0]["violation"] == "priority_preservation_violation"
                    repair = repair_slot_for(task, "intervention")
                    assert repair not in json.dumps(loop["violations"])
                    assert loop["first_assignments"] == task["oracle"]["intervention"]["first"]
                    assert loop["retry_assignments"] == task["oracle"]["intervention"]["assignments"]
                    assert loop["first_assignments"]["agent_a"] != task["protection"]["slot"]
                else:
                    assert loop["nack_path"] is False
            drop_c, _ = _run(tmp, task, "control", "drop_protection")
            assert drop_c["full_pass"] == 1, (task["id"], drop_c["process_profile"])
            drop_i, drop_i_loop = _run(tmp, task, "intervention", "drop_protection")
            assert drop_i["measurement_valid"]
            assert drop_i["full_pass"] == 0
            assert drop_i["process_profile"]["first_error"] == "protection_revision_not_delivered"
            assert drop_i_loop["b_ran"] is True
            assert drop_i_loop["protection_delivered"] is False
            assert drop_i_loop["nack_path"] is False
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
        channel.put_private("agent_b", {"secret": "protect_a_et_v2"})
        assert channel.read_private("agent_a", "agent_b")["reason"] == "unauthorized_private_read"
        assert channel.read_private("coordinator", "agent_b")["reason"] == "unauthorized_private_read"
        assert channel.submit_claim(role="coordinator", agent_id="agent_a", slot="et81", plan_version="plan-001")["ok"] is False
        _, loop = _run(tmp, task, "intervention", "multi")
        for token in leak_tokens_for(task, "intervention"):
            assert token not in loop["prompts"]["agent_a_report"]
            assert token not in loop["prompts"]["agent_b_report"]
            assert token not in loop["prompts"]["coordinator_initial"]
            assert token in loop["prompts"]["coordinator_retry"]
        text = Path(loop["world_path"]).read_text(encoding="utf-8")
        assert "ENVIRONMENT_REWRITE" not in text
        assert loop["env_denied"] is True
        _, dropped = _run(tmp, task, "intervention", "drop_protection")
        for token in leak_tokens_for(task, "intervention"):
            assert token not in dropped["prompts"]["coordinator_retry"]


def test_deviations():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        def keep_first(_p):
            first = task["oracle"]["intervention"]["first"]
            return _dump({"plan_version": "plan-001", "assignments": first, "rule": "priority_keep_then_earliest_free"})

        cell, loop = _run(tmp, task, "intervention", "multi", retry_fn=keep_first)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] in {"retry_not_recovered", "invalid_joint_assignment"}
        assert loop["nack_path"] is True

        def clash(_p):
            slot = task["protection"]["slot"]
            return _dump({"plan_version": "plan-001", "assignments": {"agent_a": slot, "agent_b": slot}, "rule": "priority_keep_then_earliest_free"})

        cell, loop = _run(tmp, task, "intervention", "multi", retry_fn=clash)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "constraint_regression"

        def plan002(_p):
            first = task["oracle"]["intervention"]["first"]
            return _dump(
                {
                    "plan_version": "plan-002",
                    "assignments": {"agent_a": first["agent_a"], "agent_b": task["slots"][2]},
                    "rule": "priority_keep_then_earliest_free",
                }
            )

        cell, loop = _run(tmp, task, "intervention", "multi", retry_fn=plan002)
        assert cell["measurement_valid"], cell
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "retry_plan_version_invalid"
        assert cell["extra"]["contract_compliance"] is False
        assert cell["extra"]["model_evaluable"] is True
        assert loop["plan_error"] == "retry_plan_version_invalid"
        assert loop["plan"]["assignments"]

        def deviate(_p):
            return _dump({"agent_id": "agent_b", "plan_version": "plan-001", "confirm": True, "slot": task["slots"][2]})

        cell, _ = _run(tmp, task, "control", "multi", commit_b_fn=deviate)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "execution_deviated_from_plan"


def test_fairness():
    from exp_gm_c1_03.fairness import preflight

    check = preflight()
    assert check["ok"], check["leaks"]


def main() -> int:
    test_not_old_items()
    print("new C1-03 tasks, not prior C1 items")
    test_oracle_unique()
    print("Oracle unique; intervention first plan deterministically violates protection")
    test_direct_rule()
    print("Rule Direct pass")
    test_rule_tracks()
    print("Multi both variants pass; intervention enters NACK; Drop protection / coordinator as specified")
    test_privacy_and_env()
    print("privacy, coordinator cannot execute, env rewrite denied, NACK does not name repair slot")
    test_deviations()
    print("retry-same / constraint regression / execution deviate / plan-002 contract failure caught")
    test_fairness()
    print("fairness pass")
    print("EXP-GM-C1-03 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
