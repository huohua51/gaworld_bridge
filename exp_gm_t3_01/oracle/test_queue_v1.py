from main import can_join


def test_under_v1_cap():
    assert can_join(49) is True


def test_at_v1_cap():
    assert can_join(50) is False


def test_v2_cutover_still_open():
    assert can_join(40) is True
