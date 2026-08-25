#!/usr/bin/env python3
"""Rule calibration for EXP-GM-N1. Must pass before any GLM run."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from exp_gm_n1.contract import KEEP, REVISE, decision_contract
from exp_gm_n1.loader import leak_tokens_for, load_tasks
from exp_gm_n1.loop import run_cell
from exp_gm_n1.prompts import rule_decision, rule_relay, rule_source
from exp_gm_n1.scorer import score_cell


def _source(task, variant):
    return lambda _p: json.dumps(rule_source(task, variant), ensure_ascii=False)


def _relay(task):
    def _fn(prompt: str):
        # Rule agent does not parse the prompt; loop already isolated the inbox.
        return json.dumps({"_": "replaced"}, ensure_ascii=False)

    return _fn


def _run(tmp: Path, task: dict, variant: str, track: str) -> tuple[dict, dict]:
    def source_fn(_p: str) -> str:
        return json.dumps(rule_source(task, variant), ensure_ascii=False)

    def relay_fn(_p: str) -> str:
        # Reconstruct from the private state the Source just sent: Rule reads channel via loop.
        # The loop passes raw inbox into the prompt; Rule here uses the task private path.
        payload = rule_source(task, variant)
        relay = rule_relay(task, [payload], task["source_id"])
        return json.dumps(relay, ensure_ascii=False)

    def decision_fn(prompt: str) -> str:
        # Extract inbox from the rendered prompt's JSON is fragile; Rule uses loop-equivalent:
        # We parse 【收件箱】 from the prompt.
        marker = "【收件箱】"
        inbox = []
        if marker in prompt:
            raw = prompt.split(marker, 1)[1].split("\n【", 1)[0].strip()
            inbox = json.loads(raw)
        return json.dumps(rule_decision(task, inbox=inbox), ensure_ascii=False)

    loop = run_cell(
        task=task,
        variant=variant,
        track=track,
        task_id=f"{task['id']}_{variant}_{track}_rule",
        out_dir=tmp / f"{task['id']}_{variant}_{track}",
        source_fn=source_fn,
        relay_fn=relay_fn,
        decision_fn=decision_fn,
    )
    cell = score_cell(
        task=task,
        variant=variant,
        track=track,
        repeat_id=0,
        loop=loop,
        workflow_id="exp_gm_n1_rule",
        instance_id=f"{task['id']}_{variant}_{track}",
    )
    return cell, loop


def test_privacy_and_path():
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for task in load_tasks():
            for variant in ("control", "intervention"):
                cells = {}
                loops = {}
                for track in ("direct", "full", "drop"):
                    cell, loop = _run(tmp, task, variant, track)
                    cells[track] = cell
                    loops[track] = loop
                    assert loop["relay_ran"] is True
                    assert loop["budget"]["calls"] == 3
                    assert loop["budget"]["kinds"] == ["source", "relay", "decision"]
                    assert loop["peek_source"]["reason"] == "unauthorized_private_read"
                    assert loop["peek_verifier"]["reason"] == "unauthorized_private_read"
                    if variant == "control":
                        for token in leak_tokens_for(task, "intervention"):
                            assert token not in loop["first_prompt"]
                assert cells["direct"]["full_pass"] == 1, (task["id"], variant, cells["direct"]["process_profile"])
                assert cells["full"]["full_pass"] == 1, (task["id"], variant, cells["full"]["process_profile"])
                if variant == "control":
                    assert cells["drop"]["full_pass"] == 1
                    assert loops["drop"]["decision"]["action"] == KEEP
                else:
                    assert cells["drop"]["full_pass"] == 0
                    assert loops["drop"]["executor_saw_message"] is False
                    assert loops["full"]["executor_saw_message"] is True
                    assert loops["direct"]["executor_saw_message"] is True
                    assert loops["direct"]["decision"]["action"] == REVISE
                    assert loops["full"]["decision"]["action"] == REVISE
                    assert loops["drop"]["decision"]["action"] == KEEP
                    for token in leak_tokens_for(task, "intervention"):
                        assert token not in loops["drop"]["decision_prompt"]


def test_wrong_approve_not_needed():
    ok, reason = decision_contract({"action": KEEP, "evidence_message_id": "m1"})
    assert reason == "ok"
    _, extra = decision_contract({"action": KEEP, "evidence_message_id": "m1", "target": "x"})
    assert extra == "keep_carries_revision_fields"
    _, missing = decision_contract({"action": REVISE, "evidence_message_id": "m2"})
    assert missing == "revise_missing_revision_fields"


def main() -> int:
    test_privacy_and_path()
    print("privacy, Source→Relay→DM, Drop discard, equal budget, Rule Direct/Full pass, Drop intervention fail: pass")
    test_wrong_approve_not_needed()
    print("keep/revise schema: pass")
    print("EXP-GM-N1 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
