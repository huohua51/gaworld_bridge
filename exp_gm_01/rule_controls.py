#!/usr/bin/env python3
"""Rule calibration for EXP-GM-01. Must pass before GLM."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from exp_gm_01.loop import run_cell_loop
from exp_gm_01.probes import PROBES
from exp_gm_01.roles import action_contract, rule_agent
from exp_gm_01.scoring import process_success, score_cell
from gaworld.life.venue import VenueEventChannel
from v0_first_batch.paths import GAWORLD_ROOT, ensure_import_paths

TRACKS = ("direct_current_state", "full_event", "drop_event")
VARIANTS = ("control", "intervention")


def _city_map():
    ensure_import_paths()
    os.chdir(GAWORLD_ROOT)
    from city_map_system import load_city_map

    return load_city_map("citymap.md")


def _run(tmp: Path, probe: dict, variant: str, track: str, city_map: dict):
    def agent(notice, _schedule):
        return rule_agent(probe, notice=notice)

    return run_cell_loop(
        probe=probe,
        variant=variant,
        track=track,
        task_id=f"{probe['id']}_{variant}_{track}_rule",
        out_dir=tmp / f"{probe['id']}_{variant}_{track}",
        agent_fn=agent,
        city_map=city_map,
    )


def test_action_contract_rejects_nested_review():
    probe = PROBES[0]
    nested = {
        "decision": "revise",
        "mismatches": [{"path": "x", "old_value": 1, "new_value": 2}],
        "required_change": {"path": "x"},
    }
    payload, reason = action_contract(probe, nested)
    assert reason == "fields_not_extractable"
    ok, reason_ok = action_contract(
        probe,
        {
            "action": "update_visit",
            "destination": probe["original"],
            "slot_id": probe["slot_id"],
            "adopted_state_version": "v1",
            "evidence_event_id": "evt-1",
        },
    )
    assert reason_ok == "ok"
    assert ok["destination"] == probe["original"]


def test_rule_direct_and_full_pass_both_variants():
    city = _city_map()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for probe in PROBES:
            for track in ("direct_current_state", "full_event"):
                for variant in VARIANTS:
                    loop = _run(tmp, probe, variant, track, city)
                    cell = score_cell(
                        probe=probe,
                        variant=variant,
                        track=track,
                        seed=0,
                        loop=loop,
                        workflow_id="rule",
                        instance_id=loop["task_id"],
                    )
                    target = (loop.get("action") or {}).get("destination") == loop["oracle_destination"]
                    assert cell["measurement_valid"] is True, (probe["id"], track, variant, cell)
                    assert cell["extra"]["target_correct"] is True, (probe["id"], track, variant, cell["process_profile"])
                    assert process_success(track, target_correct=target, r3=cell["process_profile"]["r3"]) is True
                    assert cell["full_pass"] == 1, (probe["id"], track, variant, cell["process_profile"]["first_error"])


def test_rule_drop_is_not_clean():
    city = _city_map()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for probe in PROBES:
            for variant in VARIANTS:
                loop = _run(tmp, probe, variant, "drop_event", city)
                cell = score_cell(
                    probe=probe,
                    variant=variant,
                    track="drop_event",
                    seed=0,
                    loop=loop,
                    workflow_id="rule",
                    instance_id=loop["task_id"],
                )
                assert cell["measurement_valid"] is True, (probe["id"], variant)
                assert cell["full_pass"] == 0
                if variant == "control":
                    assert cell["extra"]["target_correct"] is True
                    assert cell["process_profile"]["first_error"] == "event_not_delivered"
                else:
                    assert cell["extra"]["target_correct"] is False
                    assert cell["process_profile"]["first_error"] == "destination_closed"


def test_environment_cannot_submit():
    city = _city_map()
    with tempfile.TemporaryDirectory() as raw:
        channel = VenueEventChannel(str(Path(raw) / "v.jsonl"), city_map=city)
        out = channel.reject_submit("t", "environment")
        assert out["ok"] is False
        assert out["reason"] == "unauthorized_action_submit"


def main() -> int:
    test_action_contract_rejects_nested_review()
    print("action contract: pass")
    test_environment_cannot_submit()
    print("permissions: pass")
    test_rule_direct_and_full_pass_both_variants()
    print("rule direct/full: pass")
    test_rule_drop_is_not_clean()
    print("rule drop: pass")
    print("EXP-GM-01 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
