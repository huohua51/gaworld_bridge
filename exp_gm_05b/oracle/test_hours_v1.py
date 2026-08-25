from main import can_work


def test_must_be_certified():
    assert can_work(False, 10) is False
    assert can_work(True, 10) is True


def test_v1_hours_inclusive():
    assert can_work(True, 40) is True
    assert can_work(True, 41) is False


def test_v1_allows_36():
    assert can_work(True, 36) is True
