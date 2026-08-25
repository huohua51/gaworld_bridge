"""Deterministic Rule controls for 04d protocol on development and held-out tasks."""

from __future__ import annotations

from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04d.loop import run_cell_loop
from exp_gm_04d.protocol import freeze_ok
from exp_gm_04d.roles import rule_executor, rule_reviewer
from exp_gm_04d.tasks import DEV_TASKS, HELD_OUT_TASKS


def _fns(task):
    def executor(brief: str, review):
        version = "v2" if review and review.get("decision") == "revise" else "v1"
        if "70000" in brief or "返还率 0.5" in brief or "总预算 80" in brief:
            version = "v2"
        if "129" in brief or "达到 21" in brief or "降到 15" in brief:
            version = "v2"
        return rule_executor(task, version=version, review=review)

    def reviewer(draft: str, private: dict):
        return rule_reviewer(draft, task, private)

    return executor, reviewer


def _run(tmp: Path, task, variant: str, track: str):
    exe, rev = _fns(task)
    return run_cell_loop(
        task=task,
        variant=variant,
        track=track,
        task_id=f"{task['id']}_{variant}_{track}_rule",
        out_dir=tmp / f"{task['id']}_{variant}_{track}",
        executor_fn=exe,
        reviewer_fn=rev,
        brief_v1=task["v1"]["brief"],
        brief_v2=task["v2"]["brief"],
    )


def test_freeze_rule():
    assert freeze_ok("approve", []) is True
    assert freeze_ok("revise", []) is False
    assert freeze_ok("revise", [{"patch_id": "patch-01"}]) is True
    assert freeze_ok("approve", [{"patch_id": "patch-01"}]) is False


def test_rule_dev_full_review_both_variants(tmp_path: Path):
    task = DEV_TASKS[0]
    for variant, key in (("control", "v1"), ("intervention", "v2")):
        loop = _run(tmp_path, task, variant, "full_review")
        assert score_hidden_tests(loop["final_path"], task[key]["oracle"])["passed"] is True
        assert loop["false_positive_revision"] is False
        if variant == "control":
            assert (loop.get("review_action") or {}).get("decision") == "approve"
        else:
            assert loop["patch_adoption"] is True


def test_rule_held_out_full_review_both_variants(tmp_path: Path):
    task = HELD_OUT_TASKS[0]
    for variant, key in (("control", "v1"), ("intervention", "v2")):
        loop = _run(tmp_path, task, variant, "full_review")
        assert score_hidden_tests(loop["final_path"], task[key]["oracle"])["passed"] is True, (variant, loop.get("events"))
        other = "v2" if key == "v1" else "v1"
        assert score_hidden_tests(loop["final_path"], task[other]["oracle"])["passed"] is False


def test_rule_drop_intervention_fails(tmp_path: Path):
    task = DEV_TASKS[0]
    loop = _run(tmp_path, task, "intervention", "drop_review")
    assert score_hidden_tests(loop["final_path"], task["v2"]["oracle"])["passed"] is False
    assert loop["inbox_empty"] is True
