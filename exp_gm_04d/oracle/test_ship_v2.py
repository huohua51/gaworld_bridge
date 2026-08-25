from main import can_ship


def test_ship_old_and_new():
    assert can_ship(99) == "ship"


def test_ship_between_old_and_new():
    assert can_ship(100) == "ship"


def test_hold_above_new():
    assert can_ship(130) == "hold"
