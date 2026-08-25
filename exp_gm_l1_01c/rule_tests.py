#!/usr/bin/env python3
"""Rule calibration for EXP-GM-L1-01c. Must pass before GLM."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from exp_gm_l1_01c.loader import BANNED, load_task, load_tasks, resume_step_for, solve_outputs, solve_step
from exp_gm_l1_01c.loop import run_cell, run_direct
from exp_gm_l1_01c.prompts import rule_checkpoint, rule_direct, rule_handoff, rule_resume, rule_step
from exp_gm_l1_01c.scorer import score_cell
from gaworld.work.continuity import CHECKPOINT_VERSION, WorkflowCheckpointChannel, next_step


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _fns(task: dict, variant: str):
    def step1(_p):
        return _dump(rule_step(task, "worker_a", task["step_ids"][0]))

    def checkpoint(_p):
        first = task["step_ids"][0]
        return _dump(rule_checkpoint(task, "worker_a", [first], {first: solve_outputs(task)[first]}))

    def handoff(prompt: str):
        ck = {}
        if "【已送达检查点】" in prompt:
            ck = json.loads(prompt.split("【已送达检查点】", 1)[1].split("\n", 1)[0])
        return _dump(rule_handoff(task, variant, ck))

    successor = "worker_b" if variant == "intervention" else "worker_a"

    def resume(prompt: str):
        ck = json.loads(prompt.split("【检查点】", 1)[1].split("\n", 1)[0]) if "【检查点】" in prompt else None
        ho = json.loads(prompt.split("【接替指令】", 1)[1].split("\n", 1)[0]) if "【接替指令】" in prompt else None
        if ck is None:
            ck = {}
        return _dump(rule_resume(task, successor, ck if ck else None, ho if ho else None))

    def step2(_p):
        prior = {task["step_ids"][0]: solve_outputs(task)[task["step_ids"][0]]}
        return _dump(rule_step(task, successor, task["step_ids"][1], prior))

    def step3(_p):
        outputs = solve_outputs(task)
        prior = {task["step_ids"][0]: outputs[task["step_ids"][0]], task["step_ids"][1]: outputs[task["step_ids"][1]]}
        return _dump(rule_step(task, successor, task["step_ids"][2], prior))

    return step1, checkpoint, handoff, resume, step2, step3


def _run(tmp: Path, task: dict, variant: str, track: str, **overrides):
    step1, checkpoint, handoff, resume, step2, step3 = _fns(task, variant)
    loop = run_cell(
        task=task,
        variant=variant,
        track=track,
        out_dir=tmp / f"{task['id']}_{variant}_{track}",
        step1_fn=overrides.get("step1_fn", step1),
        checkpoint_fn=overrides.get("checkpoint_fn", checkpoint),
        handoff_fn=overrides.get("handoff_fn", handoff),
        resume_fn=overrides.get("resume_fn", resume),
        step2_fn=overrides.get("step2_fn", step2),
        step3_fn=overrides.get("step3_fn", step3),
    )
    cell = score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=0,
        loop=loop,
        workflow_id="exp_gm_l1_01c_rule",
        instance_id=f"{task['id']}_{variant}_{track}",
    )
    return cell, loop


def test_not_old_items():
    ids = {task["id"] for task in load_tasks()}
    assert ids == {"l1_01c_gas_cylinder_001", "l1_01c_balance_check_001", "l1_01c_label_intake_001"}
    for task in load_tasks():
        blob = json.dumps(task, default=str)
        for token in BANNED:
            assert token not in blob, token


def test_oracle_unique():
    for task in load_tasks():
        solved = solve_outputs(task)
        for variant in ("control", "intervention"):
            want = task["oracle"][variant]
            assert want["outputs"] == solved, (task["id"], variant)
            assert want["resume_step"] == resume_step_for(task) == task["step_ids"][1]
            assert want["interrupt"] == (variant == "intervention")
            assert want["actor_by_step"][task["step_ids"][0]] == "worker_a"
            if variant == "intervention":
                assert want["actor_by_step"][task["step_ids"][1]] == "worker_b"
            else:
                assert want["actor_by_step"][task["step_ids"][1]] == "worker_a"
            assert next_step(task["step_ids"], [task["checkpoint_after"]]) == want["resume_step"]


def test_label_intake_copies_ids():
    task = load_task("l1_01c_label_intake_001")
    out = solve_outputs(task)
    blob = json.dumps(out)
    assert "checksum" not in blob
    assert out["label_ck52"] == {"verified_ids": ["L9", "L10"], "missing_ids": []}
    assert out["label_st53"] == {"bin": "S8", "sealed": True}
    assert solve_step(task, "label_ck52", {"label_rx51": out["label_rx51"]}) == out["label_ck52"]


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
                    workflow_id="l101_direct",
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
                assert loop["checkpoint_created"] is True
                assert loop["world"]["checkpoint"]["checkpoint_version"] == CHECKPOINT_VERSION
                if variant == "intervention":
                    assert loop["successor"] == "worker_b"
                    assert loop["resume_declared"] == task["step_ids"][1]
                    assert loop["world"]["steps"][task["step_ids"][0]]["actor"] == "worker_a"
                    assert loop["world"]["steps"][task["step_ids"][1]]["actor"] == "worker_b"
                    assert loop["duplicates"] == []
                    assert loop["recovery_latency"] is not None
                else:
                    assert loop["successor"] == "worker_a"
                    assert all(body["actor"] == "worker_a" for body in loop["world"]["steps"].values())
            drop_c, _ = _run(tmp, task, "control", "drop_checkpoint")
            assert drop_c["full_pass"] == 1, (task["id"], drop_c["process_profile"])
            drop_i, drop_i_loop = _run(tmp, task, "intervention", "drop_checkpoint")
            assert drop_i["measurement_valid"]
            assert drop_i["full_pass"] == 0
            assert drop_i["process_profile"]["first_error"] == "checkpoint_not_delivered"
            assert drop_i_loop["b_ran"] is True
            ho_c, _ = _run(tmp, task, "control", "drop_handoff")
            assert ho_c["full_pass"] == 1, (task["id"], ho_c["process_profile"])
            ho_i, ho_loop = _run(tmp, task, "intervention", "drop_handoff")
            assert ho_i["measurement_valid"]
            assert ho_i["full_pass"] == 0
            assert ho_i["process_profile"]["first_error"] == "handoff_not_delivered"
            assert ho_loop["coordinator_ran"] is True


def test_privacy_and_env():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        channel = WorkflowCheckpointChannel(step_ids=list(task["step_ids"]), path=tmp / "c.jsonl")
        channel.put_private("worker_a", {"secret": "worker_a_offline_inv_v1"})
        assert channel.read_private("worker_b", "worker_a")["reason"] == "unauthorized_private_read"
        assert channel.read_private("coordinator", "worker_a")["reason"] == "unauthorized_private_read"
        assert channel.execute_step(role="coordinator", step_id=task["step_ids"][0], output={"x": 1})["ok"] is False
        assert channel.execute_step(role="environment", step_id=task["step_ids"][0], output={"x": 1})["reason"] == "environment_fallback"
        _, loop = _run(tmp, task, "intervention", "multi")
        token = task["interrupt_token"]
        assert token not in loop["prompts"]["worker_a_step1"]
        assert token in loop["prompts"]["coordinator_handoff"]
        text = Path(loop["world_path"]).read_text(encoding="utf-8")
        assert "ENVIRONMENT_REWRITE" not in text
        assert loop["env_denied"] is True
        _, control = _run(tmp, task, "control", "multi")
        assert token not in control["prompts"]["coordinator_handoff"]


def test_deviations():
    task = load_tasks()[0]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)

        def redo_first(_p):
            first = task["step_ids"][0]
            return _dump(rule_step(task, "worker_b", first))

        cell, loop = _run(tmp, task, "intervention", "multi", step2_fn=redo_first)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "duplicate_action"
        assert loop["duplicates"]

        def skip_to_last(_p):
            last = task["step_ids"][2]
            return _dump(rule_step(task, "worker_b", last, solve_outputs(task)))

        cell, _ = _run(tmp, task, "intervention", "multi", step2_fn=skip_to_last)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] in {"resume_from_wrong_step", "remaining_step_skipped", "workflow_not_completed"}

        def skip_coord(_p):
            last = task["step_ids"][2]
            return _dump(
                {
                    "successor": "worker_a",
                    "checkpoint_version": CHECKPOINT_VERSION,
                    "completed_steps": [task["step_ids"][0]],
                    "resume_step": last,
                    "remaining_steps": [last],
                }
            )

        cell, _ = _run(tmp, task, "control", "multi", handoff_fn=skip_coord)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "resume_from_wrong_step"

        def pollute(_p):
            first = task["step_ids"][0]
            last = task["step_ids"][2]
            return _dump(
                {
                    "worker_id": "worker_a",
                    "completed_steps": [first],
                    "outputs": {first: solve_outputs(task)[first], last: solve_outputs(task)[last]},
                }
            )

        cell, _ = _run(tmp, task, "control", "multi", checkpoint_fn=pollute)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "checkpoint_content_incorrect"

        def stale(_p):
            return _dump({"worker_id": "worker_b", "checkpoint_version": "ckpt-000", "resume_step": task["step_ids"][1]})

        cell, _ = _run(tmp, task, "intervention", "multi", resume_fn=stale)
        assert cell["full_pass"] == 0
        assert cell["process_profile"]["first_error"] == "stale_checkpoint_used"


def test_fairness():
    from exp_gm_l1_01c.fairness import preflight

    check = preflight()
    assert check["ok"], check["leaks"]


def main() -> int:
    test_not_old_items()
    print("new L1-01 tasks, not prior C1/T3/N1 items")
    test_oracle_unique()
    print("Oracle unique; control A finishes, intervention B resumes at step 2")
    test_label_intake_copies_ids()
    print("label intake copies received_ids, no checksum")
    test_direct_rule()
    print("Rule Direct pass")
    test_rule_tracks()
    print("Multi both variants pass; Drop checkpoint / handoff as specified")
    test_privacy_and_env()
    print("privacy, coordinator cannot execute, env rewrite denied")
    test_deviations()
    print("duplicate / wrong resume / stale / skip / polluted checkpoint caught")
    test_fairness()
    print("fairness pass")
    print("EXP-GM-L1-01c Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
