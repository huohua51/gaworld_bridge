from main import reorder


def test_buy_at_point():
    assert reorder(10) == "buy"


def test_wait_above():
    assert reorder(11) == "wait"


def test_buy_zero():
    assert reorder(0) == "buy"
