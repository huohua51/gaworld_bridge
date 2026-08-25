"""Three T1 scenes, one venue-close grammar."""

from __future__ import annotations

PROBES = [
    {
        "id": "restaurant_close_001",
        "activity": "去食堂吃午饭",
        "required_type": "restaurant",
        "origin": "Central Block",
        "original": "Student Canteen",
        "alternative": "Riverside Night Market",
        "distractor": "Riverside Community Hospital",
        "slot_id": "visit_1200",
        "follow_slot_id": "after_1400",
        "follow_destination": "Central Block",
        "rule": "若计划场所开放，保持原目的地；若已关闭，改去同类型仍开放且可达的替代地点，并覆盖该时段日程。",
    },
    {
        "id": "clinic_close_001",
        "activity": "去医院复诊",
        "required_type": "clinic",
        "origin": "Central Block",
        "original": "Riverside Community Hospital",
        "alternative": "East Community Clinic",
        "distractor": "Corner Mart",
        "slot_id": "visit_1200",
        "follow_slot_id": "after_1400",
        "follow_destination": "Central Block",
        "rule": "若计划场所开放，保持原目的地；若已关闭，改去同类型仍开放且可达的替代地点，并覆盖该时段日程。",
    },
    {
        "id": "store_close_001",
        "activity": "去超市采购",
        "required_type": "store",
        "origin": "Central Block",
        "original": "Riverside Supermart",
        "alternative": "Corner Mart",
        "distractor": "Student Canteen",
        "slot_id": "visit_1200",
        "follow_slot_id": "after_1400",
        "follow_destination": "Central Block",
        "rule": "若计划场所开放，保持原目的地；若已关闭，改去同类型仍开放且可达的替代地点，并覆盖该时段日程。",
    },
]


def variant_spec(probe: dict, variant: str) -> dict:
    if variant == "control":
        status, oracle, version = "open", probe["original"], "v1"
    else:
        status, oracle, version = "closed", probe["alternative"], "v2"
    return {
        "status": status,
        "oracle_destination": oracle,
        "state_version": version,
        "must_change_slot": variant == "intervention",
    }


def venues_for(probe: dict) -> dict:
    return {
        probe["original"]: {"type": probe["required_type"], "status": "open", "state_version": "v1"},
        probe["alternative"]: {"type": probe["required_type"], "status": "open", "state_version": "v1"},
        probe["distractor"]: {"type": "other", "status": "open", "state_version": "v1"},
    }


def initial_schedule(probe: dict) -> list[dict]:
    return [
        {
            "slot_id": probe["slot_id"],
            "start": "12:00",
            "end": "13:00",
            "destination": probe["original"],
            "activity": probe["activity"],
        },
        {
            "slot_id": probe["follow_slot_id"],
            "start": "14:00",
            "end": "15:00",
            "destination": probe["follow_destination"],
            "activity": "返回",
        },
    ]


def destination_enum(probe: dict) -> list[str]:
    return [probe["original"], probe["alternative"], probe["distractor"]]


def leak_tokens(probe: dict, spec: dict) -> list[str]:
    tokens = [spec["state_version"]]
    if spec["status"] == "closed":
        tokens.extend(["closed", "已关闭"])
    return tokens
