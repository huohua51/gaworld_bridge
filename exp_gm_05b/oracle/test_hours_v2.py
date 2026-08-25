from main import can_work


def test_must_be_certified():
    assert can_work(False, 10) is False
    assert can_work(True, 10) is True


def test_v2_hours_inclusive():
    assert can_work(True, 35) is True
    assert can_work(True, 36) is False


def test_v2_rejects_old_limit():
    assert can_work(True, 40) is False
