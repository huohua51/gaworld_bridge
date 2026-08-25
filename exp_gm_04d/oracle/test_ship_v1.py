from main import can_ship


def test_ship_at_old_threshold():
    assert can_ship(99) == "ship"


def test_hold_just_above_old():
    assert can_ship(100) == "hold"


def test_hold_at_new_threshold():
    assert can_ship(129) == "hold"
