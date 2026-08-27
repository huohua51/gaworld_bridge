from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from exp_hf_h1_01.extract_stimuli import blind_id, refresh_human_registry
from exp_hf_h1_01.serve import (
    RUBRIC_IDS,
    SubmissionError,
    build_human_payload,
    validate_rating,
)


def _base_body() -> dict:
    return {
        "construct": "T3",
        "task_id": "t3_ho_queue_max_001",
        "variant_code": "A",
        "collection_mode": "three_person_team",
        "team_code": "team-01",
        "session_code": "session-01",
        "role_assignments": {
            "起草人": "person-01",
            "审核员": "person-02",
            "执行人": "person-03",
        },
        "consent_confirmed": True,
        "started_at": "2026-08-27T10:00:00+00:00",
        "duration_ms": 90_000,
        "protocol_deviations": "",
        "turns": [
            {
                "t": 1,
                "role": "起草人",
                "kind": "produce",
                "body": "QUEUE_MAX = 15",
            },
            {
                "t": 2,
                "role": "审核员",
                "kind": "decide",
                "body": json.dumps(
                    {
                        "decision": "keep",
                        "evidence": {"path": "QUEUE_MAX", "observed": 15},
                        "required_changes": [],
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "t": 3,
                "role": "执行人",
                "kind": "apply",
                "body": "QUEUE_MAX = 15",
            },
        ],
    }


def test_valid_human_submission_uses_server_owned_metadata() -> None:
    body = _base_body()
    body["task_label"] = "伪造标签"
    payload = build_human_payload(body)

    assert payload["status"] == "collected"
    assert payload["task_label"] == "窗口排队上限"
    assert payload["roles"] == ["起草人", "审核员", "执行人"]
    assert payload["trace_contract_valid"] is True
    assert payload["collection"]["consent_confirmed"] is True


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (lambda body: body.update(consent_confirmed=False), "consent_required"),
        (lambda body: body.update(started_at=""), "started_at_invalid"),
        (
            lambda body: body["turns"][0].update(body=""),
            "turn_1_body_invalid",
        ),
        (
            lambda body: body["role_assignments"].update(审核员="person-01"),
            "team_mode_requires_three_unique_codes",
        ),
    ],
)
def test_invalid_human_submission_is_rejected(mutate, error: str) -> None:
    body = _base_body()
    mutate(body)
    with pytest.raises(SubmissionError, match=error):
        build_human_payload(body)


def test_i1_contract_rejects_blank_verified_fields() -> None:
    body = _base_body()
    body.update(
        construct="I1",
        task_id="pier_berth_001",
        role_assignments={
            "观察员": "person-01",
            "核验员": "person-02",
            "调度员": "person-03",
        },
        turns=[
            {
                "role": "观察员",
                "kind": "report",
                "body": json.dumps([{}, {}]),
            },
            {
                "role": "核验员",
                "kind": "verify",
                "body": json.dumps(
                    {
                        "verified_state": "",
                        "source_id": "harbor_board",
                        "state_version": "v1",
                    }
                ),
            },
            {
                "role": "调度员",
                "kind": "act",
                "body": json.dumps(
                    {
                        "action": "submit_berth",
                        "value": "dock_north",
                        "adopted_state_version": "v1",
                    }
                ),
            },
        ],
    )
    with pytest.raises(SubmissionError, match="verification_contract_invalid"):
        build_human_payload(body)


def test_rating_requires_whitelist_exact_rubric_and_range() -> None:
    scores = {item_id: 4 for item_id in RUBRIC_IDS}
    sid, rater, normalized = validate_rating(
        {"stimulus_id": "trace-abc", "rater_id": "rater-01", "scores": scores},
        {"trace-abc"},
    )
    assert (sid, rater, normalized) == ("trace-abc", "rater-01", scores)

    with pytest.raises(SubmissionError, match="unknown_stimulus"):
        validate_rating(
            {"stimulus_id": "human-secret", "rater_id": "rater-01", "scores": scores},
            {"trace-abc"},
        )
    scores[next(iter(scores))] = 8
    with pytest.raises(SubmissionError, match="score_out_of_range"):
        validate_rating(
            {"stimulus_id": "trace-abc", "rater_id": "rater-01", "scores": scores},
            {"trace-abc"},
        )


def test_refresh_adds_collected_human_with_source_neutral_id(tmp_path: Path) -> None:
    out = tmp_path / "h1"
    display = out / "stimuli" / "display"
    human = out / "stimuli" / "human"
    display.mkdir(parents=True)
    human.mkdir(parents=True)
    sid = "h1dev-t3-queue-control"
    agent_id = blind_id(sid)
    human_id = blind_id(f"{sid}-human")
    agent_view = {
        "stimulus_id": agent_id,
        "construct": "T3",
        "task_label": "窗口排队上限",
        "variant_code": "A",
        "roles": ["起草人", "审核员", "执行人"],
        "turns": [],
    }
    (display / f"{agent_id}.json").write_text(
        json.dumps(agent_view, ensure_ascii=False), encoding="utf-8"
    )
    human_trace = {
        **agent_view,
        "stimulus_id": f"{sid}-human",
        "status": "collected",
        "source_kind": "human",
        "collection": {"team_code": "private-team"},
    }
    (human / f"{sid}-human.json").write_text(
        json.dumps(human_trace, ensure_ascii=False), encoding="utf-8"
    )
    registry = {
        "n_agent": 1,
        "n_human_collected": 0,
        "n_human_slots": 1,
        "cells": [
            {
                "stimulus_id": sid,
                "human_slot": f"{sid}-human",
                "agent_blind_id": agent_id,
                "human_blind_id": human_id,
            }
        ],
    }
    (out / "STIMULUS_REGISTRY.yaml").write_text(
        yaml.safe_dump(registry), encoding="utf-8"
    )

    refreshed = refresh_human_registry(out)

    assert refreshed["n_human_collected"] == 1
    index = json.loads((display / "index.json").read_text(encoding="utf-8"))
    assert index["stimuli"] == sorted([agent_id, human_id])
    blind_view = json.loads(
        (display / f"{human_id}.json").read_text(encoding="utf-8")
    )
    assert blind_view["stimulus_id"] == human_id
    assert "human" not in human_id
    assert "source_kind" not in blind_view
    assert "collection" not in blind_view


def test_all_internal_ids_get_unique_source_neutral_blind_ids() -> None:
    internal_ids = [f"slot-{index}{suffix}" for index in range(18) for suffix in ("", "-human")]
    blinded = [blind_id(item) for item in internal_ids]
    assert len(blinded) == len(set(blinded))
    assert all(item.startswith("trace-") and "human" not in item for item in blinded)
