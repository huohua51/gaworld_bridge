from main import is_high_priority, route

CENTERS = [
    {"id": "north_open", "region": "north", "capacity": 1, "used": 0, "closed": False},
    {"id": "north_full", "region": "north", "capacity": 1, "used": 1, "closed": False},
    {"id": "south_closed", "region": "south", "capacity": 2, "used": 0, "closed": True},
    {"id": "south_open", "region": "south", "capacity": 2, "used": 0, "closed": False},
]


def test_v2_severity_6_high():
    assert is_high_priority({"severity": 6, "region": "north"}) is True


def test_v2_severity_7_high():
    assert is_high_priority({"severity": 7, "region": "north"}) is True


def test_closed_and_capacity():
    north = route({"severity": 6, "region": "north"}, CENTERS)
    assert north["center_id"] == "north_open"
    assert north["high_priority"] is True
    assert north["deadline_hours"] == 2
    south = route({"severity": 3, "region": "south"}, CENTERS)
    assert south["center_id"] == "south_open"
    assert south["high_priority"] is False
    assert south["deadline_hours"] == 8


def test_uncovered_region():
    out = route({"severity": 6, "region": "east"}, CENTERS)
    assert out["center_id"] is None
