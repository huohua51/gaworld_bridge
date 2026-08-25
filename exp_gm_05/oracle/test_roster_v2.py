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


def _two_night():
    return [
        {"worker_id": "staff_c", "shift_id": "day"},
        {"worker_id": "medic_a", "shift_id": "night"},
        {"worker_id": "medic_b", "shift_id": "night"},
    ]


def test_v2_one_night_rejected():
    assert valid_roster(_one_night(), WORKERS, SHIFTS) is False


def test_v2_two_night_ok():
    assert valid_roster(_two_night(), WORKERS, SHIFTS) is True


def test_uncertified_medic_fails():
    bad = [
        {"worker_id": "staff_c", "shift_id": "day"},
        {"worker_id": "staff_c", "shift_id": "night"},
        {"worker_id": "medic_a", "shift_id": "night"},
    ]
    assert valid_roster(bad, WORKERS, SHIFTS) is False


def test_assign_meets_night_minimum():
    out = assign(WORKERS, SHIFTS)
    assert out
    night = [item for item in out if item["shift_id"] == "night"]
    assert len(night) >= 2
    assert valid_roster(out, WORKERS, SHIFTS) is True
