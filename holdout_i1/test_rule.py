"""Deterministic Rule-role negative controls for TASK-I1."""

from __future__ import annotations

from pathlib import Path

from holdout_i1.loop import run_cell_loop
from holdout_i1.probes import PROBES
from holdout_i1.roles import parse_json_object, rule_dispatcher, rule_observer, rule_verifier
from holdout_i1.scoring import process_success
from gaworld.comm.relay import RelayChannel


def _run(tmp: Path, probe: dict, variant: str, track: str):
    def observer(signals):
        return rule_observer(probe, variant)

    def verifier(raw, private, version):
        return rule_verifier(raw, private, version)

    def dispatcher(verified, raw):
        return rule_dispatcher(probe, verified=verified, raw=raw)

    return run_cell_loop(
        probe=probe,
        variant=variant,
        track=track,
        task_id=f"{probe['id']}_{variant}_{track}_rule",
        out_dir=tmp / f"{probe['id']}_{variant}_{track}",
        observer_fn=observer,
        verifier_fn=verifier,
        dispatcher_fn=dispatcher,
    )


def test_action_contract_rejects_swap():
    from holdout_i1.roles import action_contract

    probe = PROBES[1]
    payload, reason = action_contract(
        probe, {"action": "line_west", "value": "submit_pump", "adopted_state_version": "v1", "evidence_message_id": "x"}
    )
    assert reason == "swapped_action_value"
    ok, reason_ok = action_contract(
        probe, {"action": "submit_pump", "value": "line_west", "adopted_state_version": "v1", "evidence_message_id": "x"}
    )
    assert reason_ok == "ok"


def test_parse_json_accepts_array():
    payload = parse_json_object('```json\n[{"source_id":"a","reported_state":"open"}]\n```')
    assert payload == [{"source_id": "a", "reported_state": "open"}]


def test_rule_focused_and_full_pass_both_variants(tmp_path: Path):
    probe = PROBES[0]
    for track in ("focused", "full"):
        for variant in ("control", "intervention"):
            loop = _run(tmp_path, probe, variant, track)
            target = (loop.get("action") or {}).get("value") == loop["oracle_value"]
            assert process_success(track, loop, target_correct=target, other_also=False) is True, (track, variant)


def test_rule_drop_and_no_verify_are_not_clean(tmp_path: Path):
    probe = PROBES[0]
    for track in ("drop_verified", "no_verification"):
        for variant in ("control", "intervention"):
            loop = _run(tmp_path, probe, variant, track)
            target = (loop.get("action") or {}).get("value") == loop["oracle_value"]
            assert process_success(track, loop, target_correct=target, other_also=False) is False


def test_dispatcher_cannot_read_trust_table(tmp_path: Path):
    channel = RelayChannel(str(tmp_path / "relay.jsonl"))
    channel.put_private("t", "verifier", {"trusted_source_id": "traffic_desk"})
    out = channel.read_private("t", "dispatcher", "verifier")
    assert out["ok"] is False
    assert out["reason"] == "unauthorized_private_read"


def test_verifier_cannot_submit_action(tmp_path: Path):
    channel = RelayChannel(str(tmp_path / "relay.jsonl"))
    out = channel.reject_submit("t", "verifier")
    assert out["ok"] is False
    assert out["reason"] == "unauthorized_action_submit"


def test_duplicate_verified_adopted_once(tmp_path: Path):
    channel = RelayChannel(str(tmp_path / "relay.jsonl"))
    channel.put_private("t", "verifier", {"trusted_source_id": "src_ok"})
    channel.send_raw("t", observer_id=1, message={"source_id": "src_ok", "reported_state": "main_open"})
    channel.deliver_raw("t")
    emitted = channel.emit_verified(
        "t", verifier_id=2,
        payload={"verified_state": "main_open", "source_id": "src_ok", "state_version": "v1"},
    )
    channel.deliver_verified("t")
    mid = emitted["message"]["message_id"]
    assert channel.adopt_verified("t", mid)["ok"] is True
    again = channel.adopt_verified("t", mid)
    assert again["ok"] is False
    assert again["reason"] == "verified_already_adopted"


def test_stale_verified_rejected(tmp_path: Path):
    channel = RelayChannel(str(tmp_path / "relay.jsonl"))
    channel.put_private("t", "verifier", {"trusted_source_id": "src_ok"})
    channel.send_raw("t", observer_id=1, message={"source_id": "src_ok", "reported_state": "main_open"})
    channel.deliver_raw("t")
    emitted = channel.emit_verified(
        "t", verifier_id=2,
        payload={"verified_state": "main_open", "source_id": "src_ok", "state_version": "v1"},
    )
    channel.deliver_verified("t")
    out = channel.adopt_verified("t", emitted["message"]["message_id"], current_version="v2")
    assert out["ok"] is False
    assert out["reason"] == "stale_state_used"
