from __future__ import annotations

from collections import Counter

from human_validity.h1_h4_v2.synthetic_pilot.simulate import (
    CODER_PAIRS,
    H1_ITEMS,
    HUMAN_TRACES,
    aggregate_h1,
    cohen_kappa,
    generate_h1_ratings,
    make_agent_traces,
)


def test_wave_1_assignments_match_frozen_pilot_plan() -> None:
    expected = [
        ("SYN-P01", "rev_campus_notice_001", "A"),
        ("SYN-P01", "verify_supply_arrival_001", "B"),
        ("SYN-P02", "handoff_event_materials_001", "A"),
        ("SYN-P02", "rev_volunteer_shift_001", "B"),
        ("SYN-P03", "verify_room_access_001", "A"),
        ("SYN-P03", "handoff_appointment_queue_001", "B"),
        ("SYN-P04", "handoff_appointment_queue_001", "A"),
        ("SYN-P04", "rev_campus_notice_001", "B"),
    ]
    actual = [(trace["unit_id"], trace["surface_id"], trace["condition"]) for trace in HUMAN_TRACES]
    assert actual == expected
    assert Counter(trace["family"] for trace in HUMAN_TRACES) == {
        "revision": 3,
        "verification": 2,
        "handoff": 3,
    }


def test_agent_placeholders_are_exactly_task_condition_matched() -> None:
    agents = make_agent_traces()
    assert len(agents) == len(HUMAN_TRACES) == 8
    for human, agent in zip(HUMAN_TRACES, agents, strict=True):
        assert (agent["surface_id"], agent["condition"], agent["family"]) == (
            human["surface_id"],
            human["condition"],
            human["family"],
        )
    assert sum(trace["functional_pass"] for trace in HUMAN_TRACES) == 6
    assert sum(trace["functional_pass"] for trace in agents) == 7


def test_h1_dry_run_is_balanced_and_preserves_missingness() -> None:
    humans = [{**trace, "source_kind": "synthetic_human"} for trace in HUMAN_TRACES]
    agents = [{**trace, "source_kind": "synthetic_agent"} for trace in make_agent_traces()]
    ratings = generate_h1_ratings(humans + agents)
    assert len(ratings) == 96
    assert set(Counter(row["stimulus_id"] for row in ratings).values()) == {6}
    assert sum(row[item] == "" for row in ratings for item in H1_ITEMS) == 1

    means, reliability, intervals = aggregate_h1(ratings)
    assert means["synthetic_human"]["naturalness"] > means["synthetic_agent"]["naturalness"]
    assert set(reliability) == {"naturalness", "agency", "social_responsiveness", "role_continuity"}
    assert all(lower <= mean <= upper for mean, lower, upper in intervals.values())


def test_exactly_one_semantic_label_triggers_revision() -> None:
    triggered = []
    for label, pairs in CODER_PAIRS.items():
        agreement, kappa = cohen_kappa(pairs)
        if agreement < 0.80 or kappa < 0.60:
            triggered.append(label)
    assert triggered == ["correction_adopted"]
