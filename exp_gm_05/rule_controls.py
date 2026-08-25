#!/usr/bin/env python3
"""Deterministic Rule calibration. Must pass before any GLM cell."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_05.artifacts import render_source
from exp_gm_05.drop_loop import run_drop_cell
from exp_gm_05.inspect import registered_value
from exp_gm_05.multi_loop import run_multi_cell
from exp_gm_05.roles import rule_executor, rule_reviewer
from exp_gm_05.scoring import score_cell
from exp_gm_05.single_loop import run_single_cell
from exp_gm_05.tasks import TASKS
from gaworld.work.review import ReviewChannel


def _fns(task: dict):
    def executor(brief: str, source: str | None, review):
        return rule_executor(task, version="v1", review=review, current=source)

    def reviewer(draft: str, private: dict):
        return rule_reviewer(draft, task, private)

    return executor, reviewer


def _run(tmp: Path, task: dict, variant: str, track: str) -> dict:
    exe, rev = _fns(task)
    runners = {"single": run_single_cell, "multi": run_multi_cell, "drop": run_drop_cell}
    return runners[track](
        task=task,
        variant=variant,
        task_id=f"{task['id']}_{variant}_{track}_rule",
        out_dir=tmp / f"{task['id']}_{variant}_{track}",
        executor_fn=exe,
        reviewer_fn=rev,
    )


def _score(tmp: Path, task: dict, variant: str, track: str) -> dict:
    loop = _run(tmp, task, variant, track)
    return score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=0,
        loop=loop,
        workflow_id="exp_gm_05_rule",
        instance_id=f"{task['id']}_{variant}_{track}",
    ), loop


def test_oracle_exclusive():
    for task in TASKS:
        v1 = render_source(task, "v1")
        v2 = render_source(task, "v2")
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            p1 = tmp / "v1.py"
            p2 = tmp / "v2.py"
            p1.write_text(v1, encoding="utf-8")
            p2.write_text(v2, encoding="utf-8")
            assert score_hidden_tests(str(p1), task["v1"]["oracle"])["passed"] is True, task["id"]
            assert score_hidden_tests(str(p1), task["v2"]["oracle"])["passed"] is False, task["id"]
            assert score_hidden_tests(str(p2), task["v2"]["oracle"])["passed"] is True, task["id"]
            assert score_hidden_tests(str(p2), task["v1"]["oracle"])["passed"] is False, task["id"]


def test_rule_tracks(tmp: Path):
    for task in TASKS:
        single_c, _ = _score(tmp, task, "control", "single")
        single_i, _ = _score(tmp, task, "intervention", "single")
        multi_c, _ = _score(tmp, task, "control", "multi")
        multi_i, multi_loop = _score(tmp, task, "intervention", "multi")
        drop_c, _ = _score(tmp, task, "control", "drop")
        drop_i, drop_loop = _score(tmp, task, "intervention", "drop")
        assert single_c["full_pass"] == 1, task["id"]
        assert single_i["full_pass"] == 1, task["id"]
        assert multi_c["full_pass"] == 1, task["id"]
        assert multi_i["full_pass"] == 1, task["id"]
        assert drop_c["full_pass"] == 1, task["id"]
        assert drop_i["full_pass"] == 0, task["id"]
        assert (drop_i.get("extra") or {}).get("first_error") == "review_not_delivered"
        assert registered_value(multi_loop["final"], task) == task["change_v2"][task["path"]]
        assert registered_value(drop_loop["final"], task) == task["change_v1"][task["path"]]
        assert drop_loop["budget_valid"] is True
        assert single_c["measurement_valid"] is True


def test_permissions(tmp: Path):
    channel = ReviewChannel(str(tmp / "review.jsonl"))
    denied = channel.write_artifact(
        task_id="t", role="reviewer", kind="final", path=str(tmp / "stolen.py"), content="x"
    )
    assert denied["ok"] is False
    assert denied["reason"] == "unauthorized_artifact_write"
    assert not (tmp / "stolen.py").exists()
    channel.put_private("t", "reviewer", {"oracle": "hidden"})
    priv = channel.read_private("t", "executor")
    assert priv["ok"] is False
    assert priv["reason"] == "unauthorized_private_read"


def test_negative_scoring(tmp: Path):
    task = TASKS[0]
    v1 = render_source(task, "v1")
    version_only = v1.replace('SPEC_VERSION = "v1"', 'SPEC_VERSION = "v2"')
    claimed = v1 + '\nAPPLIED_PATCH_IDS = ["patch-01"]\n'
    extra = v1 + "\nUNREGISTERED_FLAG = 1\n"
    both = render_source(task, "v1")  # v1 should not pass v2

    def _fake(source: str, review: dict) -> dict:
        path = tmp / "neg" / "artifact_after.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        (tmp / "neg" / "artifact_before.py").write_text(v1, encoding="utf-8")
        path.write_text(source, encoding="utf-8")
        loop = {
            "events": ["requirement_available", "draft_created", "review_started", "review_decision", "review_delivered"],
            "draft": v1,
            "final": source,
            "draft_path": str(tmp / "neg" / "artifact_before.py"),
            "final_path": str(path),
            "review": review,
            "review_delivered": True,
            "budget_valid": True,
            "leak_on_first_brief": [],
            "hidden_in_prompt": [],
            "reviewer_write": {"ok": False, "reason": "unauthorized_artifact_write"},
            "executor_private": {"ok": False, "reason": "unauthorized_private_read"},
        }
        return score_cell(
            task=task, variant="intervention", track="multi", repeat_id=0, loop=loop,
            workflow_id="neg", instance_id="neg",
        )

    revise = {
        "decision": "revise",
        "reviewed_spec_version": "v1",
        "required_spec_version": "v2",
        "criterion_id": task["criterion_id"],
        "evidence": "x",
        "required_change": dict(task["change_v2"]),
    }
    assert _fake(claimed, revise)["full_pass"] == 0
    assert (_fake(claimed, revise).get("extra") or {}).get("declared_patch_adoption") is True
    assert _fake(version_only, revise)["full_pass"] == 0
    assert _fake(extra, revise)["full_pass"] == 0
    assert score_hidden_tests(str(tmp / "skip.py") if False else None, task["v1"]["oracle"])["passed"] is False


def main() -> int:
    test_oracle_exclusive()
    print("oracle exclusive: pass")
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_permissions(tmp)
        print("permissions: pass")
        test_negative_scoring(tmp)
        print("negative scoring: pass")
        test_rule_tracks(tmp)
        print("rule tracks: pass")
    print("EXP-GM-05 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
