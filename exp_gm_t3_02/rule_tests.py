#!/usr/bin/env python3
"""Rule calibration for EXP-GM-T3-02. Must pass before GLM."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_t3_01.loader import leak_tokens_for, load_tasks
from exp_gm_t3_02.integrity import IntegrityMailbox
from exp_gm_t3_02.loop import generate_shared_draft, run_track_from_draft
from exp_gm_t3_02.prompts import rule_builder_draft, rule_executor, rule_review
from exp_gm_t3_02.scorer import score_cell
from gaworld.work.review import ReviewChannel


def _generate(task):
    return lambda _p: rule_builder_draft(task)


def _draft_from_prompt(prompt: str, task: dict) -> str:
    marker = "\n【当前草稿】\n"
    if marker in prompt:
        return prompt.split(marker, 1)[1]
    return rule_builder_draft(task)


def _reviewer(task, variant):
    return lambda draft: rule_review(task, variant, draft)


def _fork(tmp: Path, task: dict, variant: str):
    shared = generate_shared_draft(
        task=task, variant=variant, repeat_id=0, out_dir=tmp / f"{task['id']}_{variant}_shared", generate_fn=_generate(task),
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
            revise_fn=lambda prompt, review, t=task: rule_executor(t, _draft_from_prompt(prompt, t), review),
            reviewer_fn=_reviewer(task, variant),
            drop=drop,
        )
        cell = score_cell(
            task=task, variant=variant, track=track, repeat_id=0, loop=loop,
            workflow_id="exp_gm_t3_02_rule", instance_id=f"{task['id']}_{variant}_{track}",
        )
        out[track] = (cell, loop)
    return out, shared


def test_rule_tracks():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            control, shared_c = _fork(tmp, task, "control")
            interv, shared_i = _fork(tmp, task, "intervention")
            for track in ("single", "multi"):
                assert control[track][0]["full_pass"] == 1, (task["id"], "control", track, control[track][0]["process_profile"])
                assert interv[track][0]["full_pass"] == 1, (task["id"], "intervention", track, interv[track][0]["process_profile"])
            assert control["drop"][0]["full_pass"] == 1, (task["id"], control["drop"][0]["process_profile"])
            assert interv["drop"][0]["full_pass"] == 0
            assert interv["drop"][0]["process_profile"]["first_error"] == "review_payload_not_delivered"
            hashes_c = {control[t][1]["shared_draft_sha256"] for t in ("single", "multi", "drop")}
            hashes_i = {interv[t][1]["shared_draft_sha256"] for t in ("single", "multi", "drop")}
            assert hashes_c == {shared_c["sha256"]}
            assert hashes_i == {shared_i["sha256"]}
            for track in ("single", "multi", "drop"):
                assert control[track][1]["budget"]["calls"] == 3
                assert control[track][1]["budget"]["kinds"] == ["builder_draft", "review", "builder_final"]
                assert interv[track][1]["reviewer_ran"] is True
            assert interv["drop"][1]["executor_saw_review"] is False
            assert interv["drop"][1]["drop_inbox_empty"] is True
            assert interv["multi"][1]["payload_trace"]["reviewer_output_hash"] == interv["multi"][1]["payload_trace"]["channel_sent_hash"]
            assert interv["multi"][1]["payload_trace"]["channel_sent_hash"] == interv["multi"][1]["payload_trace"]["executor_read_hash"]
            for token in leak_tokens_for(task, "intervention"):
                assert token not in shared_i["draft_prompt"]


def test_payload_mutated():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        shared = generate_shared_draft(task=task, variant="intervention", repeat_id=0, out_dir=tmp / "s", generate_fn=_generate(task))

        def mutate(mailbox: IntegrityMailbox) -> None:
            mailbox.mutate_stored(lambda payload: payload["required_changes"][0].__setitem__("new_value", 1))

        loop = run_track_from_draft(
            task=task, variant="intervention", track="multi", task_id="mut",
            out_dir=tmp / "m", shared=shared,
            revise_fn=lambda prompt, review: rule_executor(task, _draft_from_prompt(prompt, task), review),
            reviewer_fn=_reviewer(task, "intervention"),
            mutate_fn=mutate,
        )
        cell = score_cell(task=task, variant="intervention", track="multi", repeat_id=0, loop=loop, workflow_id="neg", instance_id="mut")
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "review_payload_mutated"


def test_executor_did_not_read():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        shared = generate_shared_draft(task=task, variant="intervention", repeat_id=0, out_dir=tmp / "s", generate_fn=_generate(task))
        loop = run_track_from_draft(
            task=task, variant="intervention", track="multi", task_id="noread",
            out_dir=tmp / "m", shared=shared,
            revise_fn=lambda prompt, review: rule_executor(task, _draft_from_prompt(prompt, task), review),
            reviewer_fn=_reviewer(task, "intervention"),
            skip_inbox=True,
        )
        cell = score_cell(task=task, variant="intervention", track="multi", repeat_id=0, loop=loop, workflow_id="neg", instance_id="noread")
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "executor_did_not_read_payload"
        assert loop["payload_trace"]["executor_read_hash"] == loop["payload_trace"]["reviewer_output_hash"]


def test_partial_change():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        shared = generate_shared_draft(task=task, variant="intervention", repeat_id=0, out_dir=tmp / "s", generate_fn=_generate(task))

        def reviewer(_draft):
            payload = rule_review(task, "intervention", _draft)
            payload["required_changes"].append(
                {"change_id": "change-02", "path": "SPEC_VERSION", "old_value": "v1", "new_value": "v2"}
            )
            return payload

        def revise(prompt, review):
            only = dict(review)
            only["required_changes"] = list(review.get("required_changes") or [])[:1]
            return rule_executor(task, _draft_from_prompt(prompt, task), only)

        loop = run_track_from_draft(
            task=task, variant="intervention", track="multi", task_id="partial",
            out_dir=tmp / "m", shared=shared, revise_fn=revise, reviewer_fn=reviewer,
        )
        cell = score_cell(task=task, variant="intervention", track="multi", repeat_id=0, loop=loop, workflow_id="neg", instance_id="partial")
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "partial_change_applied"


def test_environment_and_reviewer_acl():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        channel = ReviewChannel(str(tmp / "r.jsonl"))
        denied = channel.write_artifact(task_id="t", role="reviewer", kind="final", path=str(tmp / "x.py"), content="x")
        assert denied["reason"] == "unauthorized_artifact_write"
        env = channel.write_artifact(task_id="t", role="environment", kind="final", path=str(tmp / "y.py"), content="ENVIRONMENT_REWRITE = 1\n")
        assert env.get("ok") is False
        assert not (tmp / "y.py").exists()
        channel.put_private("t", "reviewer", {"spec": "hidden"})
        priv = channel.read_private("t", "executor")
        assert priv["reason"] == "unauthorized_private_read"

    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        control, _ = _fork(tmp, task, "control")
        loop = control["multi"][1]
        assert "ENVIRONMENT_REWRITE" not in Path(loop["final_path"]).read_text(encoding="utf-8")
        assert not (Path(loop["final_path"]).parent / "stolen.py").exists()
        assert loop["environment_write"]["ok"] is False
        assert loop["reviewer_write"]["reason"] == "unauthorized_artifact_write"


def test_fairness_prompts():
    from exp_gm_t3_02.fairness import preflight

    check = preflight()
    assert check["ok"], check["leaks"]


def main() -> int:
    test_rule_tracks()
    print("Rule Single/Multi control+intervention pass; Drop control pass; Drop intervention fail")
    test_payload_mutated()
    print("mutated payload: review_payload_mutated")
    test_executor_did_not_read()
    print("executor skip inbox: executor_did_not_read_payload")
    test_partial_change()
    print("partial field apply: partial_change_applied")
    test_environment_and_reviewer_acl()
    print("environment rewrite denied; reviewer cannot write")
    test_fairness_prompts()
    print("fairness prompts: pass")
    print("EXP-GM-T3-02 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
