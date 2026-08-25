"""Three T2 household-care scenes with registered eligibility, not moral judgment."""

from __future__ import annotations

from gaworld.life.family import NONE

PROBES = [
    {
        "id": "child_fever_001",
        "activity": "儿童发热照料",
        "patient_id": "child-01",
        "legal_caregiver_id": "parent-01",
        "distractor_id": "neighbor-01",
        "conflict_slot_id": "work-slot-01",
        "conflict_activity": "上班",
        "registered_expense": 200,
        "requires_care": True,
        "rule": "仅当登记照料事件 requires_care=true 时，合法照料者认领责任、取消冲突日程并登记一次规定支出；否则保持原日程、不认领、支出为 0。不要自行判断是否值得照料。",
    },
    {
        "id": "elder_clinic_001",
        "activity": "老人临时就医",
        "patient_id": "elder-01",
        "legal_caregiver_id": "adult-child-01",
        "distractor_id": "neighbor-01",
        "conflict_slot_id": "shopping-slot-02",
        "conflict_activity": "采购",
        "registered_expense": 300,
        "requires_care": True,
        "rule": "仅当登记照料事件 requires_care=true 时，合法照料者认领责任、取消冲突日程并登记一次规定支出；否则保持原日程、不认领、支出为 0。不要自行判断是否值得照料。",
    },
    {
        "id": "postop_pickup_001",
        "activity": "家庭成员术后接送",
        "patient_id": "patient-01",
        "legal_caregiver_id": "spouse-01",
        "distractor_id": "neighbor-01",
        "conflict_slot_id": "leisure-slot-03",
        "conflict_activity": "休闲",
        "registered_expense": 120,
        "requires_care": True,
        "rule": "仅当登记照料事件 requires_care=true 时，合法照料者认领责任、取消冲突日程并登记一次规定支出；否则保持原日程、不认领、支出为 0。不要自行判断是否值得照料。",
    },
]


def variant_spec(probe: dict, variant: str) -> dict:
    if variant == "control":
        return {
            "requires_care": False,
            "state_version": "v1",
            "oracle_action": "keep_schedule",
            "oracle_caregiver": NONE,
            "oracle_patient": NONE,
            "oracle_event": NONE,
            "oracle_decision": "keep",
            "oracle_expense": 0,
            "oracle_evidence": NONE,
        }
    return {
        "requires_care": True,
        "state_version": "v2",
        "oracle_action": "provide_care",
        "oracle_caregiver": probe["legal_caregiver_id"],
        "oracle_patient": probe["patient_id"],
        "oracle_event": None,
        "oracle_decision": "cancel",
        "oracle_expense": int(probe["registered_expense"]),
        "oracle_evidence": None,
    }


def household_for(probe: dict) -> dict:
    return {
        "patient_id": probe["patient_id"],
        "legal_caregiver_id": probe["legal_caregiver_id"],
        "distractor_id": probe["distractor_id"],
        "conflict_slot_id": probe["conflict_slot_id"],
        "registered_expense": int(probe["registered_expense"]),
        "requires_care": False,
        "members": [probe["legal_caregiver_id"], probe["patient_id"], probe["distractor_id"]],
    }


def initial_schedule(probe: dict) -> list[dict]:
    return [
        {
            "slot_id": probe["conflict_slot_id"],
            "start": "10:00",
            "end": "12:00",
            "activity": probe["conflict_activity"],
            "status": "planned",
        },
        {
            "slot_id": "home-slot-04",
            "start": "19:00",
            "end": "20:00",
            "activity": "在家",
            "status": "planned",
        },
    ]


def caregiver_enum(probe: dict) -> list[str]:
    return [probe["legal_caregiver_id"], probe["distractor_id"], NONE]


def patient_enum(probe: dict) -> list[str]:
    return [probe["patient_id"], NONE]
