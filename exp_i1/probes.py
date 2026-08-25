"""Three social scenes, one communication grammar."""

from __future__ import annotations

PROBES = [
    {
        "id": "road_status_001",
        "action": "submit_route",
        "trusted_source_id": "traffic_desk",
        "rumor_source_id": "street_chat",
        "state_a": "main_open",
        "state_b": "main_closed",
        "value_a": "main_route",
        "value_b": "alternate_route",
        "rule": "若核实状态是 main_open，提交 main_route；若是 main_closed，提交 alternate_route。",
    },
    {
        "id": "shelter_capacity_001",
        "action": "submit_shelter",
        "trusted_source_id": "city_roster",
        "rumor_source_id": "crowd_post",
        "state_a": "shelter_open",
        "state_b": "shelter_full",
        "value_a": "send_to_A",
        "value_b": "send_to_B",
        "rule": "若核实状态是 shelter_open，提交 send_to_A；若是 shelter_full，提交 send_to_B。",
    },
    {
        "id": "clinic_service_001",
        "action": "submit_clinic",
        "trusted_source_id": "clinic_board",
        "rumor_source_id": "hallway_talk",
        "state_a": "clinic_open",
        "state_b": "clinic_paused",
        "value_a": "clinic_A",
        "value_b": "clinic_B",
        "rule": "若核实状态是 clinic_open，提交 clinic_A；若是 clinic_paused，提交 clinic_B。",
    },
]


def variant_spec(probe: dict, variant: str) -> dict:
    if variant == "control":
        trusted_state, rumor_state, value, version = (
            probe["state_a"],
            probe["state_b"],
            probe["value_a"],
            "v1",
        )
    else:
        trusted_state, rumor_state, value, version = (
            probe["state_b"],
            probe["state_a"],
            probe["value_b"],
            "v2",
        )
    return {
        "trusted_state": trusted_state,
        "rumor_state": rumor_state,
        "oracle_value": value,
        "state_version": version,
        "signals": [
            {"source_id": probe["trusted_source_id"], "reported_state": trusted_state},
            {"source_id": probe["rumor_source_id"], "reported_state": rumor_state},
        ],
    }


def leak_tokens(probe: dict) -> list[str]:
    return [
        probe["trusted_source_id"],
        "trusted_source_id",
        "可信来源",
    ]
