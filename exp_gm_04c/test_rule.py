"""Deterministic Rule-role negative controls. Must pass before live GLM."""

from __future__ import annotations

from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_04c.loop import run_cell_loop
from exp_gm_04c.roles import rule_executor, rule_reviewer
from exp_gm_04c.tasks import TASKS
from gaworld.work.review import ReviewChannel


def _fns(task):
    def executor(brief: str, review):
        version = "v2" if ("70000" in brief or "返还率 0.5" in brief or "总预算 80" in brief) else "v1"
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


def test_rule_full_review_passes_both_variants(tmp_path: Path):
    task = TASKS[0]
    for variant, oracle_key in (("control", "v1"), ("intervention", "v2")):
        loop = _run(tmp_path, task, variant, "full_review")
        scored = score_hidden_tests(loop["final_path"], task[oracle_key]["oracle"])
        assert scored["passed"] is True, variant
        other = score_hidden_tests(loop["final_path"], task["v2" if oracle_key == "v1" else "v1"]["oracle"])
        assert other["passed"] is False


def test_rule_drop_review_control_passes_intervention_fails(tmp_path: Path):
    task = TASKS[0]
    control = _run(tmp_path, task, "control", "drop_review")
    intervention = _run(tmp_path, task, "intervention", "drop_review")
    assert score_hidden_tests(control["final_path"], task["v1"]["oracle"])["passed"] is True
    assert score_hidden_tests(intervention["final_path"], task["v2"]["oracle"])["passed"] is False
    assert intervention["inbox_empty"] is True


def test_reviewer_cannot_write_final(tmp_path: Path):
    channel = ReviewChannel(str(tmp_path / "review.jsonl"))
    out = channel.write_artifact(
        task_id="t",
        role="reviewer",
        kind="final",
        path=str(tmp_path / "final_main.py"),
        content="stolen",
    )
    assert out["ok"] is False
    assert out["reason"] == "unauthorized_artifact_write"
    assert not (tmp_path / "final_main.py").exists()


def test_executor_cannot_read_private_v2(tmp_path: Path):
    channel = ReviewChannel(str(tmp_path / "review.jsonl"))
    channel.put_private("t", "reviewer", {"spec_version": "v2", "reservation_wage": 70000})
    out = channel.read_private("t", "executor")
    assert out["ok"] is False
    assert out["reason"] == "unauthorized_private_read"


def test_stale_review_rejected(tmp_path: Path):
    channel = ReviewChannel(str(tmp_path / "review.jsonl"))
    draft = tmp_path / "draft_main.py"
    draft.write_text('SPEC_VERSION = "v2"\n', encoding="utf-8")
    channel.put_private("t", "reviewer", {"spec_version": "v2"})
    channel.submit_draft("t", executor_id=5, path=str(draft), spec_version="v2")
    channel.request_review("t")
    emitted = channel.emit_review(
        "t",
        reviewer_id=6,
        payload={
            "decision": "revise",
            "reviewed_spec_version": "v2",
            "required_spec_version": "v1",
            "criterion_id": "reservation_wage_threshold",
            "evidence": "old",
            "required_change": {"reservation_wage": 60000},
        },
    )
    channel.deliver_review("t")
    out = channel.adopt_review("t", emitted["action"]["review_id"], current_spec_version="v2")
    assert out["ok"] is False
    assert out["reason"] == "stale_review"


def test_duplicate_review_adopted_once(tmp_path: Path):
    channel = ReviewChannel(str(tmp_path / "review.jsonl"))
    draft = tmp_path / "draft_main.py"
    draft.write_text('SPEC_VERSION = "v1"\n', encoding="utf-8")
    channel.put_private("t", "reviewer", {"spec_version": "v2"})
    channel.submit_draft("t", executor_id=5, path=str(draft), spec_version="v1")
    channel.request_review("t")
    emitted = channel.emit_review(
        "t",
        reviewer_id=6,
        payload={
            "decision": "revise",
            "reviewed_spec_version": "v1",
            "required_spec_version": "v2",
            "criterion_id": "reservation_wage_threshold",
            "evidence": "60000",
            "required_change": {"reservation_wage": 70000},
        },
    )
    channel.deliver_review("t")
    rid = emitted["action"]["review_id"]
    first = channel.adopt_review("t", rid, current_spec_version="v1")
    again = channel.adopt_review("t", rid, current_spec_version="v1")
    assert first["ok"] is True
    assert again["ok"] is False
    assert again["reason"] == "review_already_adopted"
