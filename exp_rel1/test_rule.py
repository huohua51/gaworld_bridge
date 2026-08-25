"""Deterministic Rule-role negative controls for TASK-REL1."""

from __future__ import annotations

from pathlib import Path

from exp_rel1.loop import run_cell_loop
from exp_rel1.probes import PROBES, variant_spec
from exp_rel1.roles import parse_json_object, rule_dispatcher, rule_observer, rule_trust_updater
from exp_rel1.scoring import process_success
from gaworld.comm.trust import TrustLedger


def _run(tmp: Path, probe: dict, variant: str, track: str):
    def observer(signals):
        return rule_observer(probe, variant)

    def updater(history, currents, version, phase):
        return rule_trust_updater(history, currents, version, phase)

    def dispatcher(trust, currents, round_name):
        return rule_dispatcher(probe, trust=trust, round_name=round_name)

    return run_cell_loop(
        probe=probe,
        variant=variant,
        track=track,
        task_id=f"{probe['id']}_{variant}_{track}_rule",
        out_dir=tmp / f"{probe['id']}_{variant}_{track}",
        observer_fn=observer,
        updater_fn=updater,
        dispatcher_fn=dispatcher,
    )


def test_parse_json_accepts_array():
    payload = parse_json_object('```json\n[{"person_id":"a","reported_state":"open"}]\n```')
    assert payload == [{"person_id": "a", "reported_state": "open"}]


def test_current_reports_identical_across_variants():
    probe = PROBES[0]
    a = variant_spec(probe, "control")
    b = variant_spec(probe, "intervention")
    assert a["signals"] == b["signals"]
    assert a["formation_value"] != b["formation_value"]
    assert a["update_value"] != b["update_value"]
    assert a["formation_value"] == b["update_value"]
    assert a["update_value"] == b["formation_value"]


def test_rule_focused_and_full_pass_both_variants(tmp_path: Path):
    probe = PROBES[0]
    for track in ("focused", "full"):
        for variant in ("control", "intervention"):
            loop = _run(tmp_path, probe, variant, track)
            formation = (loop.get("formation_action") or {}).get("value") == loop["oracle_formation"]
            update = (loop.get("update_action") or {}).get("value") == loop["oracle_update"]
            assert process_success(
                track, loop, formation_correct=formation, update_correct=update, other_also=False
            ) is True, (track, variant, loop.get("events"), loop.get("formation_action"), loop.get("update_action"))


def test_rule_drop_and_no_history_are_not_clean(tmp_path: Path):
    probe = PROBES[0]
    for track in ("drop_trust", "no_history"):
        for variant in ("control", "intervention"):
            loop = _run(tmp_path, probe, variant, track)
            formation = (loop.get("formation_action") or {}).get("value") == loop["oracle_formation"]
            update = (loop.get("update_action") or {}).get("value") == loop["oracle_update"]
            assert process_success(
                track, loop, formation_correct=formation, update_correct=update, other_also=False
            ) is False


def test_dispatcher_cannot_read_history(tmp_path: Path):
    channel = TrustLedger(str(tmp_path / "trust.jsonl"))
    channel.put_history("t", "trust_updater", [{"round": 1, "outcome": "open"}])
    out = channel.read_history("t", "dispatcher")
    assert out["ok"] is False
    assert out["reason"] == "unauthorized_history_read"


def test_trust_updater_cannot_submit_action(tmp_path: Path):
    channel = TrustLedger(str(tmp_path / "trust.jsonl"))
    out = channel.reject_submit("t", "trust_updater")
    assert out["ok"] is False
    assert out["reason"] == "unauthorized_action_submit"
