from main import assign, valid_roster

WORKERS = [
    {"id": "medic_a", "certified": ["medic"]},
    {"id": "medic_b", "certified": ["medic"]},
    {"id": "staff_c", "certified": []},
]
SHIFTS = [
    {"id": "day", "slot": "day", "hours": 8, "role": "staff", "kind": "day"},
    {"id": "night", "slot": "night", "hours": 8, "role": "medic", "kind": "night"},
]


def _one_night():
    return [
        {"worker_id": "staff_c", "shift_id": "day"},
        {"worker_id": "medic_a", "shift_id": "night"},
    ]


def test_v1_one_night_ok():
    assert valid_roster(_one_night(), WORKERS, SHIFTS) is True


def test_uncertified_medic_fails():
    bad = [
        {"worker_id": "staff_c", "shift_id": "day"},
        {"worker_id": "staff_c", "shift_id": "night"},
    ]
    assert valid_roster(bad, WORKERS, SHIFTS) is False


def test_hours_overflow():
    bad = [
        {"worker_id": "staff_c", "shift_id": "day"},
        {"worker_id": "medic_a", "shift_id": "day"},
        {"worker_id": "medic_a", "shift_id": "night"},
    ]
    assert valid_roster(bad, WORKERS, SHIFTS) is False


def test_assign_covers_all_slots():
    out = assign(WORKERS, SHIFTS)
    assert out
    assert valid_roster(out, WORKERS, SHIFTS) is True
    assert {item["shift_id"] for item in out} == {"day", "night"}
