from main import can_join


def test_under_v2_cap():
    assert can_join(39) is True


def test_at_v2_cap():
    assert can_join(40) is False


def test_v1_cutover_now_full():
    assert can_join(49) is False
