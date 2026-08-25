#!/usr/bin/env python3
"""Rule calibration for 05b L1. Must pass before GLM."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_05b.artifacts import render_source
from exp_gm_05b.direct_loop import run_direct_cell
from exp_gm_05b.inspect import registered_value
from exp_gm_05b.review_loop import run_review_cell
from exp_gm_05b.roles import rule_executor, rule_reviewer
from exp_gm_05b.scoring import score_cell
from exp_gm_05b.tasks import TASKS
from gaworld.work.review import ReviewChannel


def test_oracle_exclusive():
    for task in TASKS:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            p1, p2 = tmp / "v1.py", tmp / "v2.py"
            p1.write_text(render_source(task, "v1"), encoding="utf-8")
            p2.write_text(render_source(task, "v2"), encoding="utf-8")
            assert score_hidden_tests(str(p1), task["v1"]["oracle"])["passed"] is True, task["id"]
            assert score_hidden_tests(str(p1), task["v2"]["oracle"])["passed"] is False, task["id"]
            assert score_hidden_tests(str(p2), task["v2"]["oracle"])["passed"] is True, task["id"]
            assert score_hidden_tests(str(p2), task["v1"]["oracle"])["passed"] is False, task["id"]


def test_rule_direct():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in TASKS:
            for variant in ("control", "intervention"):
                version = "v1" if variant == "control" else "v2"

                def executor(brief: str, _task=task, _version=version) -> str:
                    return render_source(_task, _version)

                loop = run_direct_cell(
                    task=task,
                    variant=variant,
                    task_id=f"{task['id']}_{variant}_direct",
                    out_dir=tmp / f"{task['id']}_{variant}",
                    executor_fn=executor,
                )
                cell = score_cell(
                    task=task, variant=variant, track="direct_final_spec", repeat_id=0,
                    loop=loop, workflow_id="rule", instance_id=f"{task['id']}_{variant}",
                )
                assert cell["extra"]["target_correct"] is True, task["id"]


def test_rule_review_tracks():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in TASKS:
            def executor(brief, source, review, _task=task):
                return rule_executor(_task, review=review, current=source)

            def reviewer(draft, private, _task=task):
                return rule_reviewer(draft, _task, private)

            for variant, track, drop, expect in (
                ("control", "single", False, 1),
                ("intervention", "single", False, 1),
                ("control", "multi", False, 1),
                ("intervention", "multi", False, 1),
                ("control", "drop", True, 1),
                ("intervention", "drop", True, 0),
            ):
                loop = run_review_cell(
                    task=task, variant=variant, track=track,
                    task_id=f"{task['id']}_{variant}_{track}",
                    out_dir=tmp / f"{task['id']}_{variant}_{track}",
                    executor_fn=executor, reviewer_fn=reviewer, drop=drop,
                )
                cell = score_cell(
                    task=task, variant=variant, track=track, repeat_id=0,
                    loop=loop, workflow_id="rule", instance_id=f"{task['id']}_{variant}_{track}",
                )
                assert cell["full_pass"] == expect, (task["id"], variant, track)
                if track == "drop" and variant == "intervention":
                    assert cell["extra"]["first_error"] == "review_not_delivered"
                    assert registered_value(loop["final"], task) == task["change_v1"][task["path"]]


def test_permissions_and_partial():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        channel = ReviewChannel(str(tmp / "r.jsonl"))
        denied = channel.write_artifact(task_id="t", role="reviewer", kind="final", path=str(tmp / "x.py"), content="x")
        assert denied["reason"] == "unauthorized_artifact_write"
        task = TASKS[0]
        partial = (
            'SPEC_VERSION = "v2"\nMIN_AGE = 18\nINCOME_CAP = 45000\n\n'
            "def eligible(age, income):\n    return int(age) >= MIN_AGE\n"
        )
        path = tmp / "artifact_after.py"
        path.write_text(partial, encoding="utf-8")
        draft = render_source(task, "v1")
        (tmp / "artifact_before.py").write_text(draft, encoding="utf-8")
        loop = {
            "events": ["draft_created", "review_decision", "review_delivered"],
            "draft": draft,
            "final": partial,
            "draft_path": str(tmp / "artifact_before.py"),
            "final_path": str(path),
            "review": {
                "decision": "revise",
                "reviewed_spec_version": "v1",
                "required_spec_version": "v2",
                "criterion_id": "income_cap",
                "evidence": "x",
                "required_change": {"income_cap": 45000},
            },
            "review_delivered": True,
            "budget_valid": True,
            "reviewer_write": {"ok": False, "reason": "unauthorized_artifact_write"},
            "executor_private": {"ok": False, "reason": "unauthorized_private_read"},
        }
        cell = score_cell(
            task=task, variant="intervention", track="multi", repeat_id=0,
            loop=loop, workflow_id="neg", instance_id="partial",
        )
        assert cell["full_pass"] == 0
        assert cell["extra"]["verified_patch_adoption"] is True
        assert cell["extra"]["first_error"] == "partial_change_applied"

        version_only = render_source(task, "v1").replace('SPEC_VERSION = "v1"', 'SPEC_VERSION = "v2"')
        (tmp / "version_only.py").write_text(version_only, encoding="utf-8")
        loop["final"] = version_only
        loop["final_path"] = str(tmp / "version_only.py")
        cell = score_cell(
            task=task, variant="intervention", track="multi", repeat_id=0,
            loop=loop, workflow_id="neg", instance_id="version_only",
        )
        assert cell["full_pass"] == 0
        assert cell["extra"]["first_error"] == "change_acknowledged_not_applied"

        declared_only = version_only + '\nAPPLIED_PATCH_IDS = ["income_cap"]\n'
        (tmp / "declared.py").write_text(declared_only, encoding="utf-8")
        loop["final"] = declared_only
        loop["final_path"] = str(tmp / "declared.py")
        cell = score_cell(
            task=task, variant="intervention", track="multi", repeat_id=0,
            loop=loop, workflow_id="neg", instance_id="declared_only",
        )
        assert cell["full_pass"] == 0
        assert cell["extra"]["acknowledgement_execution_gap"] is True

        extra_field = render_source(task, "v2") + "THRESHOLD = 80\n"
        (tmp / "extra.py").write_text(extra_field, encoding="utf-8")
        loop["final"] = extra_field
        loop["final_path"] = str(tmp / "extra.py")
        cell = score_cell(
            task=task, variant="intervention", track="multi", repeat_id=0,
            loop=loop, workflow_id="neg", instance_id="unregistered",
        )
        assert cell["full_pass"] == 0
        assert cell["extra"]["first_error"] == "unregistered_change"


def main() -> int:
    test_oracle_exclusive()
    print("oracle exclusive: pass")
    test_rule_direct()
    print("rule direct: pass")
    test_permissions_and_partial()
    print("permissions/partial: pass")
    test_rule_review_tracks()
    print("rule review tracks: pass")
    print("EXP-GM-05b Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
