from main import reorder


def test_buy_old_point_still_below_new():
    assert reorder(10) == "buy"


def test_buy_between_old_and_new():
    assert reorder(11) == "buy"


def test_wait_above_new():
    assert reorder(16) == "wait"
