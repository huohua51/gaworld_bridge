#!/usr/bin/env python3
"""Rule calibration for EXP-GM-05c. Must pass before GLM."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_05b.artifacts import render_source
from exp_gm_05c.contract import collect_review_action, parse_review_action, retry_prompt
from exp_gm_05c.fork_loop import generate_shared_draft, run_track_from_draft
from exp_gm_05c.inspect import registered_value, sha256_text
from exp_gm_05c.roles import rule_builder_draft, rule_builder_revise, rule_reviewer
from exp_gm_05c.scoring import score_cell
from exp_gm_05c.tasks import TASKS, leak_tokens_for
from gaworld.work.review import ReviewChannel


def _generate(task: dict):
    def _fn(_brief: str) -> str:
        return rule_builder_draft(task)

    return _fn


def _revise(task: dict):
    def _fn(_brief: str, source: str, review):
        return rule_builder_revise(task, review=review, current=source)

    return _fn


def _reviewer(task: dict):
    def _fn(draft: str, private: dict):
        return rule_reviewer(draft, task, private)

    return _fn


def _score_fork(tmp: Path, task: dict, variant: str) -> dict[str, tuple[dict, dict]]:
    shared = generate_shared_draft(
        task=task,
        variant=variant,
        repeat_id=0,
        out_dir=tmp / f"{task['id']}_{variant}_shared",
        generate_fn=_generate(task),
    )
    out = {}
    for track, drop in (("single", False), ("multi", False), ("drop", True)):
        loop = run_track_from_draft(
            task=task,
            variant=variant,
            track=track,
            task_id=f"{task['id']}_{variant}_{track}_rule",
            out_dir=tmp / f"{task['id']}_{variant}_{track}",
            shared=shared,
            revise_fn=_revise(task),
            reviewer_fn=_reviewer(task),
            drop=drop,
        )
        cell = score_cell(
            task=task,
            variant=variant,
            track=track,
            repeat_id=0,
            loop=loop,
            workflow_id="exp_gm_05c_rule",
            instance_id=f"{task['id']}_{variant}_{track}",
        )
        out[track] = (cell, loop)
    return out, shared


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


def test_rule_tracks_and_shared_hash():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in TASKS:
            control, shared_c = _score_fork(tmp, task, "control")
            interv, shared_i = _score_fork(tmp, task, "intervention")
            assert control["single"][0]["full_pass"] == 1, task["id"]
            assert control["multi"][0]["full_pass"] == 1, task["id"]
            assert control["drop"][0]["full_pass"] == 1, task["id"]
            assert interv["single"][0]["full_pass"] == 1, task["id"]
            assert interv["multi"][0]["full_pass"] == 1, task["id"]
            assert interv["drop"][0]["full_pass"] == 0, task["id"]
            assert (interv["drop"][0].get("extra") or {}).get("first_error") == "review_not_delivered"
            hashes_c = {control[t][1]["shared_draft_sha256"] for t in ("single", "multi", "drop")}
            hashes_i = {interv[t][1]["shared_draft_sha256"] for t in ("single", "multi", "drop")}
            assert hashes_c == {shared_c["sha256"]}
            assert hashes_i == {shared_i["sha256"]}
            assert shared_c["sha256"] == sha256_text(shared_c["source"])
            assert not shared_c["leak_on_first_brief"]
            assert not shared_i["leak_on_first_brief"]
            for token in leak_tokens_for(task, "intervention"):
                assert token not in shared_i["generation_prompt"]
            for track in ("single", "multi", "drop"):
                assert control[track][1]["budget_valid"] is True
                assert interv[track][1]["budget"]["calls"] == 3
                assert control[track][1]["budget"]["calls"] == interv[track][1]["budget"]["calls"]
            assert registered_value(interv["multi"][1]["final"], task) == task["change_v2"][task["path"]]
            assert registered_value(interv["drop"][1]["final"], task) == task["change_v1"][task["path"]]
            assert interv["drop"][1]["v2_published_after_draft"] is True


def test_permissions_and_declared_not_applied():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        channel = ReviewChannel(str(tmp / "r.jsonl"))
        denied = channel.write_artifact(task_id="t", role="reviewer", kind="final", path=str(tmp / "x.py"), content="x")
        assert denied["reason"] == "unauthorized_artifact_write"
        channel.put_private("t", "reviewer", {"spec": "hidden"})
        priv = channel.read_private("t", "executor")
        assert priv["reason"] == "unauthorized_private_read"
        task = TASKS[0]
        v1 = render_source(task, "v1")
        claimed = v1 + '\nAPPLIED_PATCH_IDS = ["income_cap"]\n'
        path = tmp / "artifact_after.py"
        path.write_text(claimed, encoding="utf-8")
        (tmp / "artifact_before.py").write_text(v1, encoding="utf-8")
        review = {
            "decision": "revise",
            "mismatches": [{"path": task["path"], "observed": 50000, "required": 45000}],
            "required_change": {"path": task["path"], "old_value": 50000, "new_value": 45000},
        }
        loop = {
            "events": ["draft_created", "review_decision", "review_delivered"],
            "draft": v1,
            "final": claimed,
            "draft_path": str(tmp / "artifact_before.py"),
            "final_path": str(path),
            "review": review,
            "review_delivered": True,
            "budget_valid": True,
            "contract_ok": True,
            "leak_on_first_brief": [],
            "hidden_in_prompt": [],
            "shared_draft_sha256": sha256_text(v1),
            "v2_published_after_draft": True,
            "reviewer_write": {"ok": False, "reason": "unauthorized_artifact_write"},
            "executor_private": {"ok": False, "reason": "unauthorized_private_read"},
        }
        cell = score_cell(
            task=task, variant="intervention", track="multi", repeat_id=0,
            loop=loop, workflow_id="neg", instance_id="declared",
        )
        assert cell["full_pass"] == 0
        assert cell["extra"]["declared_patch_adoption"] is True
        assert cell["extra"]["acknowledgement_execution_gap"] is True
        assert cell["extra"]["first_error"] == "change_acknowledged_not_applied"


def test_review_action_contract():
    approve = '{"decision":"approve","mismatches":[],"required_change":null}'
    assert parse_review_action(approve).ok is True
    revise = (
        '{"decision":"revise","mismatches":[{"path":"income_cap","observed":50000,"required":45000}],'
        '"required_change":{"path":"income_cap","old_value":50000,"new_value":45000}}'
    )
    parsed = parse_review_action(revise)
    assert parsed.ok is True
    prose = parse_review_action("我认为这个产物需要进一步调整。")
    assert prose.ok is False
    assert prose.error == "prose_only"
    retry = retry_prompt(prose)
    assert "approve" not in retry.split("Problems")[-1] or "approve|revise" in retry
    assert "45000" not in retry
    assert "hidden" not in retry.lower()
    calls = {"n": 0}

    def _prose(_prompt: str) -> str:
        calls["n"] += 1
        return "我认为这个产物需要进一步调整。"

    failed = collect_review_action(_prose, "first")
    assert calls["n"] == 2
    assert failed.contract_retry_used is True
    assert failed.contract_retry_success is False
    assert failed.error == "model_contract_failure"
    assert parse_review_action('{"mismatches":[],"required_change":null}').error == "missing_fields"
    assert parse_review_action('{"decision":"maybe","mismatches":[],"required_change":null}').error == "invalid_enum"
    assert parse_review_action('{"decision":"revise","mismatches":[{"path":"x","observed":1,"required":2}],"required_change":null}').error == "revise_missing_change"
    assert parse_review_action('{"decision":"approve","mismatches":[{"path":"x","observed":1,"required":2}],"required_change":null}').error == "approve_has_mismatch"
    swapped = parse_review_action(
        '{"decision":"revise","mismatches":[{"path":"income_cap","observed":50000,"required":45000}],'
        '"required_change":{"path":"income_cap","old_value":45000,"new_value":50000}}'
    )
    assert swapped.ok is True
    from exp_gm_05c.scoring import review_decision_correct
    from exp_gm_05c.tasks import TASKS

    task = TASKS[0]
    draft = "INCOME_CAP = 50000\nSPEC_VERSION = \"v1\"\n"
    assert review_decision_correct("intervention", swapped.action, task, draft) is False


def main() -> int:
    test_oracle_exclusive()
    print("oracle exclusive: pass")
    test_permissions_and_declared_not_applied()
    print("permissions/declared: pass")
    test_review_action_contract()
    print("review action contract: pass")
    test_rule_tracks_and_shared_hash()
    print("rule tracks/shared hash/budget/no v2 leak: pass")
    print("EXP-GM-05c Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
