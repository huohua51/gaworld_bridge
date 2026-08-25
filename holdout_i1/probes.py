"""Three unpublished social scenes. Same communication grammar as I1."""

from __future__ import annotations

PROBES = [
    {
        "id": "pier_berth_001",
        "action": "submit_berth",
        "trusted_source_id": "harbor_board",
        "rumor_source_id": "dock_chat",
        "state_a": "berth_free",
        "state_b": "berth_busy",
        "value_a": "dock_north",
        "value_b": "dock_south",
        "rule": "若核实状态是 berth_free，提交 dock_north；若是 berth_busy，提交 dock_south。",
    },
    {
        "id": "pump_station_001",
        "action": "submit_pump",
        "trusted_source_id": "water_desk",
        "rumor_source_id": "pipe_forum",
        "state_a": "pump_online",
        "state_b": "pump_offline",
        "value_a": "line_west",
        "value_b": "line_east",
        "rule": "若核实状态是 pump_online，提交 line_west；若是 pump_offline，提交 line_east。",
    },
    {
        "id": "library_hours_001",
        "action": "submit_desk",
        "trusted_source_id": "library_board",
        "rumor_source_id": "lobby_talk",
        "state_a": "desk_open",
        "state_b": "desk_closed",
        "value_a": "hall_a",
        "value_b": "hall_b",
        "rule": "若核实状态是 desk_open，提交 hall_a；若是 desk_closed，提交 hall_b。",
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
