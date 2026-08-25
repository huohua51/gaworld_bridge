"""Three social scenes. Current reports are identical across variants."""

from __future__ import annotations

from typing import Any

PROBES = [
    {
        "id": "road_status_001",
        "action": "submit_route",
        "person_a": "neighbor_lin",
        "person_b": "passer_wu",
        "state_a": "main_open",
        "state_b": "main_closed",
        "value_a": "main_route",
        "value_b": "alternate_route",
        "rule": "若采用的信任状态是 main_open，提交 main_route；若是 main_closed，提交 alternate_route。",
    },
    {
        "id": "shelter_capacity_001",
        "action": "submit_shelter",
        "person_a": "volunteer_chen",
        "person_b": "stranger_zhao",
        "state_a": "shelter_open",
        "state_b": "shelter_full",
        "value_a": "send_to_A",
        "value_b": "send_to_B",
        "rule": "若采用的信任状态是 shelter_open，提交 send_to_A；若是 shelter_full，提交 send_to_B。",
    },
    {
        "id": "clinic_service_001",
        "action": "submit_clinic",
        "person_a": "nurse_zhou",
        "person_b": "visitor_sun",
        "state_a": "clinic_open",
        "state_b": "clinic_paused",
        "value_a": "clinic_A",
        "value_b": "clinic_B",
        "rule": "若采用的信任状态是 clinic_open，提交 clinic_A；若是 clinic_paused，提交 clinic_B。",
    },
]


def current_signals(probe: dict) -> list[dict[str, str]]:
    return [
        {"person_id": probe["person_a"], "reported_state": probe["state_a"]},
        {"person_id": probe["person_b"], "reported_state": probe["state_b"]},
    ]


def _history_row(probe: dict, round_no: int, outcome: str) -> dict[str, Any]:
    return {
        "round": round_no,
        "reports": {
            probe["person_a"]: probe["state_a"],
            probe["person_b"]: probe["state_b"],
        },
        "outcome": outcome,
    }


def variant_spec(probe: dict, variant: str) -> dict:
    """Unique change: who the past outcomes support. Current reports never change."""
    if variant == "control":
        past_outcome = probe["state_a"]
        reversal_outcome = probe["state_b"]
        formation_person = probe["person_a"]
        formation_state = probe["state_a"]
        formation_value = probe["value_a"]
        update_person = probe["person_b"]
        update_state = probe["state_b"]
        update_value = probe["value_b"]
    else:
        past_outcome = probe["state_b"]
        reversal_outcome = probe["state_a"]
        formation_person = probe["person_b"]
        formation_state = probe["state_b"]
        formation_value = probe["value_b"]
        update_person = probe["person_a"]
        update_state = probe["state_a"]
        update_value = probe["value_a"]
    return {
        "formation_person": formation_person,
        "formation_state": formation_state,
        "formation_value": formation_value,
        "update_person": update_person,
        "update_state": update_state,
        "update_value": update_value,
        "other_person_formation": probe["person_b"] if variant == "control" else probe["person_a"],
        "other_person_update": probe["person_a"] if variant == "control" else probe["person_b"],
        "formation_version": "v1",
        "update_version": "v2",
        "signals": current_signals(probe),
        "history": [
            _history_row(probe, 1, past_outcome),
            _history_row(probe, 2, past_outcome),
        ],
        "reversal": _history_row(probe, 3, reversal_outcome),
    }


def leak_tokens(probe: dict) -> list[str]:
    return [
        "history",
        "outcome",
        "历史账本",
        "正确次数",
    ]
