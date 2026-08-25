#!/usr/bin/env python3
"""Rule calibration for EXP-GM-02. Must pass before GLM."""

from __future__ import annotations

import tempfile
from pathlib import Path

from exp_gm_02.loop import run_cell_loop
from exp_gm_02.probes import PROBES
from exp_gm_02.roles import action_contract, control_placeholder, rule_agent
from exp_gm_02.scoring import score_cell
from gaworld.life.family import NONE, FamilyCareChannel
from v0_first_batch.paths import ensure_import_paths

TRACKS = ("direct_household_state", "full_family_event", "drop_family_event")
VARIANTS = ("control", "intervention")


def _run(tmp: Path, probe: dict, variant: str, track: str):
    def agent(notice, _schedule):
        return rule_agent(probe, notice=notice)

    return run_cell_loop(
        probe=probe,
        variant=variant,
        track=track,
        task_id=f"{probe['id']}_{variant}_{track}_rule",
        out_dir=tmp / f"{probe['id']}_{variant}_{track}",
        agent_fn=agent,
    )


def test_control_requires_complete_placeholders():
    probe = PROBES[0]
    missing = {"action": "keep_schedule", "expense_amount": 0}
    _, reason = action_contract(probe, missing)
    assert reason == "fields_not_extractable"
    payload, reason_ok = action_contract(probe, control_placeholder(probe))
    assert reason_ok == "ok"
    assert payload["caregiver_id"] == NONE
    assert payload["expense_amount"] == 0


def test_rule_direct_and_full_both_variants():
    ensure_import_paths()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for probe in PROBES:
            for track in ("direct_household_state", "full_family_event"):
                for variant in VARIANTS:
                    loop = _run(tmp, probe, variant, track)
                    cell = score_cell(
                        probe=probe, variant=variant, track=track, seed=0,
                        loop=loop, workflow_id="rule", instance_id=loop["task_id"],
                    )
                    assert cell["measurement_valid"] is True, (probe["id"], track, variant, cell["process_profile"])
                    assert cell["full_pass"] == 1, (probe["id"], track, variant, cell["process_profile"]["first_error"])
                    assert cell["extra"]["target_correct"] is True


def test_rule_drop_control_pass_intervention_fail():
    ensure_import_paths()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for probe in PROBES:
            control = _run(tmp, probe, "control", "drop_family_event")
            control_cell = score_cell(
                probe=probe, variant="control", track="drop_family_event", seed=0,
                loop=control, workflow_id="rule", instance_id=control["task_id"],
            )
            assert control_cell["full_pass"] == 1, (probe["id"], control_cell["process_profile"])
            intervention = _run(tmp, probe, "intervention", "drop_family_event")
            intervention_cell = score_cell(
                probe=probe, variant="intervention", track="drop_family_event", seed=0,
                loop=intervention, workflow_id="rule", instance_id=intervention["task_id"],
            )
            assert intervention_cell["full_pass"] == 0
            assert intervention_cell["process_profile"]["first_error"] == "care_event_not_delivered"
            assert intervention_cell["extra"]["target_correct"] is False


def test_environment_cannot_assign_caregiver():
    with tempfile.TemporaryDirectory() as raw:
        channel = FamilyCareChannel(str(Path(raw) / "f.jsonl"))
        denied = channel.reject_submit("t", "environment")
        assert denied["reason"] == "environment_assigned_caregiver"
        assigned = channel.assign_caregiver("t", "environment", "parent-01")
        assert assigned["reason"] == "environment_assigned_caregiver"


def main() -> int:
    test_control_requires_complete_placeholders()
    print("placeholders: pass")
    test_environment_cannot_assign_caregiver()
    print("permissions: pass")
    test_rule_direct_and_full_both_variants()
    print("rule direct/full: pass")
    test_rule_drop_control_pass_intervention_fail()
    print("rule drop: pass")
    print("EXP-GM-02 Rule calibration passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
