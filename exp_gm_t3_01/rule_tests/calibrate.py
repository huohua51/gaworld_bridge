#!/usr/bin/env python3
"""Rule calibration for EXP-GM-T3-01. Must pass before any GLM run."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_04.scorer import score_hidden_tests
from exp_gm_t3_01.artifacts import render_source
from exp_gm_t3_01.contracts.review_action import (
    APPROVE,
    CONTRACT_APPROVE_EXTRA,
    CONTRACT_REVISE_MISSING,
    REVISE,
    action_contract,
)
from exp_gm_t3_01.inspect import sha256_text
from exp_gm_t3_01.loader import load_tasks, leak_tokens_for
from exp_gm_t3_01.loop import generate_shared_draft, run_track_from_draft
from exp_gm_t3_01.roles import rule_builder_draft, rule_builder_revise, rule_reviewer
from exp_gm_t3_01.scorer import score_cell
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


def _score_fork(tmp: Path, task: dict, variant: str) -> tuple[dict, dict]:
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
            workflow_id="exp_gm_t3_01_rule",
            instance_id=f"{task['id']}_{variant}_{track}",
        )
        out[track] = (cell, loop)
    return out, shared


def test_oracle_exclusive():
    for task in load_tasks():
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            p1, p2 = tmp / "v1.py", tmp / "v2.py"
            p1.write_text(render_source(task, "v1"), encoding="utf-8")
            p2.write_text(render_source(task, "v2"), encoding="utf-8")
            assert score_hidden_tests(str(p1), task["v1"]["oracle"])["passed"] is True, task["id"]
            assert score_hidden_tests(str(p1), task["v2"]["oracle"])["passed"] is False, task["id"]
            assert score_hidden_tests(str(p2), task["v2"]["oracle"])["passed"] is True, task["id"]
            assert score_hidden_tests(str(p2), task["v1"]["oracle"])["passed"] is False, task["id"]


def test_control_approve_and_intervention_revise():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            control, shared_c = _score_fork(tmp, task, "control")
            interv, shared_i = _score_fork(tmp, task, "intervention")
            for track in ("single", "multi", "drop"):
                assert control[track][0]["full_pass"] == 1, (task["id"], track, control[track][0]["process_profile"])
                assert control[track][1]["review"]["action"] == APPROVE
            assert interv["single"][0]["full_pass"] == 1, (task["id"], interv["single"][0]["process_profile"])
            assert interv["multi"][0]["full_pass"] == 1, (task["id"], interv["multi"][0]["process_profile"])
            assert interv["drop"][0]["full_pass"] == 0
            assert (interv["drop"][0].get("extra") or {}).get("first_error") == "review_not_delivered"
            assert interv["single"][1]["review"]["action"] == REVISE
            hashes_c = {control[t][1]["shared_draft_sha256"] for t in ("single", "multi", "drop")}
            hashes_i = {interv[t][1]["shared_draft_sha256"] for t in ("single", "multi", "drop")}
            assert hashes_c == {shared_c["sha256"]}
            assert hashes_i == {shared_i["sha256"]}
            assert not shared_c["leak_on_first_brief"]
            assert not shared_i["leak_on_first_brief"]
            for token in leak_tokens_for(task, "intervention"):
                assert token not in shared_i["generation_prompt"]
            for track in ("single", "multi", "drop"):
                assert control[track][1]["budget"]["calls"] == interv[track][1]["budget"]["calls"] == 3
                assert control[track][1]["budget"]["kinds"] == ["builder_draft", "review", "builder_final"]
                assert interv[track][1]["reviewer_ran"] is True
            assert interv["drop"][1]["executor_saw_review"] is False
            assert interv["drop"][1]["drop_inbox_empty"] is True
            assert interv["multi"][1]["executor_saw_review"] is True
            assert interv["single"][1]["executor_saw_review"] is True
            assert interv["drop"][1]["final"] == interv["drop"][1]["draft"]
            assert "review_dropped" in interv["drop"][1]["events"]


def test_wrong_approve_caught():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        shared = generate_shared_draft(task=task, variant="intervention", repeat_id=0, out_dir=tmp / "s", generate_fn=_generate(task))

        def reviewer(_draft, _private):
            return {"action": APPROVE, "evidence_id": task["evidence_v2"]}

        loop = run_track_from_draft(
            task=task, variant="intervention", track="multi", task_id="wrong_approve",
            out_dir=tmp / "m", shared=shared, revise_fn=_revise(task), reviewer_fn=reviewer,
        )
        cell = score_cell(task=task, variant="intervention", track="multi", repeat_id=0, loop=loop, workflow_id="neg", instance_id="wrong_approve")
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "true_revision_missed"


def test_control_false_positive_revision_caught():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        shared = generate_shared_draft(task=task, variant="control", repeat_id=0, out_dir=tmp / "s", generate_fn=_generate(task))

        def reviewer(_draft, _private):
            return {
                "action": REVISE,
                "target": task["target"],
                "required_value": task["change_v2"][task["target"]],
                "evidence_id": task["evidence_v1"],
            }

        loop = run_track_from_draft(
            task=task, variant="control", track="multi", task_id="fp",
            out_dir=tmp / "m", shared=shared, revise_fn=_revise(task), reviewer_fn=reviewer,
        )
        cell = score_cell(task=task, variant="control", track="multi", repeat_id=0, loop=loop, workflow_id="neg", instance_id="fp")
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "false_positive_revision"


def test_declared_not_applied_caught_by_hidden_tests():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        v1 = render_source(task, "v1")
        claimed = v1 + '\nAPPLIED_PATCH_IDS = ["parking_free_minutes"]\n'
        path = tmp / "artifact_after.py"
        path.write_text(claimed, encoding="utf-8")
        (tmp / "artifact_before.py").write_text(v1, encoding="utf-8")
        review = {
            "action": REVISE,
            "target": task["target"],
            "required_value": task["change_v2"][task["target"]],
            "evidence_id": task["evidence_v2"],
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
            "budget": {"calls": 3, "kinds": ["builder_draft", "review", "builder_final"]},
            "contract_ok": True,
            "contract_error": "ok",
            "contract_rejected": False,
            "leak_on_first_brief": [],
            "hidden_in_prompt": [],
            "shared_draft_sha256": sha256_text(v1),
            "reviewer_ran": True,
            "executor_saw_review": True,
            "first_prompt": "write PARKING_FREE_MINUTES = 120",
            "review_prompt": "review the draft",
            "final_prompt": "apply request_revision",
            "reviewer_write": {"ok": False, "reason": "unauthorized_artifact_write"},
            "executor_private": {"ok": False, "reason": "unauthorized_private_read"},
        }
        cell = score_cell(task=task, variant="intervention", track="multi", repeat_id=0, loop=loop, workflow_id="neg", instance_id="declared")
        assert cell["full_pass"] == 0
        assert cell["extra"]["declared_patch_adoption"] is True
        assert cell["extra"]["acknowledgement_execution_gap"] is True
        assert cell["process_profile"]["first_error"] == "change_acknowledged_not_applied"


def test_permissions():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        channel = ReviewChannel(str(tmp / "r.jsonl"))
        denied = channel.write_artifact(task_id="t", role="reviewer", kind="final", path=str(tmp / "x.py"), content="x")
        assert denied["reason"] == "unauthorized_artifact_write"
        channel.put_private("t", "reviewer", {"spec": "hidden-private-standard"})
        priv = channel.read_private("t", "executor")
        assert priv["reason"] == "unauthorized_private_read"


def test_exclusive_contract():
    ok_keep, reason = action_contract({"action": APPROVE, "evidence_id": "e1"})
    assert reason == "ok" and ok_keep["action"] == APPROVE
    extra, extra_reason = action_contract({"action": APPROVE, "evidence_id": "e1", "target": "x", "required_value": 1})
    assert extra_reason == CONTRACT_APPROVE_EXTRA
    missing, missing_reason = action_contract({"action": REVISE, "evidence_id": "e2"})
    assert missing_reason == CONTRACT_REVISE_MISSING
    _, bad = action_contract({"decision": "approve", "mismatches": [], "required_change": None})
    assert bad == "fields_not_extractable"


def test_fairness_prompts():
    from exp_gm_t3_01.roles import builder_draft_prompt, builder_revise_prompt, reviewer_prompt, self_check_prompt
    from exp_gm_t3_01.loader import private_payload

    for task in load_tasks():
        draft_prompt = builder_draft_prompt(task["brief"])
        for token in leak_tokens_for(task, "intervention"):
            assert token not in draft_prompt, (task["id"], token)
        assert "test_parking_" not in draft_prompt
        assert "test_deposit_" not in draft_prompt
        assert "test_queue_" not in draft_prompt
        drop_final = builder_revise_prompt(task["brief"], "SPEC_VERSION = \"v1\"\n", None)
        for token in leak_tokens_for(task, "intervention"):
            assert token not in drop_final
        assert "request_revision" not in drop_final
        private = private_payload(task, "intervention")
        self_p = self_check_prompt("draft", private)
        rev_p = reviewer_prompt("draft", private)
        assert "自检" in self_p
        assert "审核员" in rev_p
        assert "自检" not in rev_p
        assert self_p.index("只输出一个 JSON 对象") < self_p.index("自检")
        assert '""}}' not in self_p
        assert '""}}' not in rev_p


def main() -> int:
    test_oracle_exclusive()
    print("1 oracle exclusive: pass")
    test_control_approve_and_intervention_revise()
    print("2/5 control approve, intervention revise, drop no v2, shared hash, equal budget: pass")
    test_wrong_approve_caught()
    print("3 wrong approve: caught")
    test_control_false_positive_revision_caught()
    print("4 control false-positive revision: caught")
    test_declared_not_applied_caught_by_hidden_tests()
    print("6 declared but file unchanged: caught")
    test_permissions()
    print("7/8 reviewer cannot write; executor cannot read private: pass")
    test_exclusive_contract()
    print("approve/revise schema: pass")
    test_fairness_prompts()
    print("first-call isolation / drop final / self-check vs reviewer: pass")
    print("EXP-GM-T3-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
