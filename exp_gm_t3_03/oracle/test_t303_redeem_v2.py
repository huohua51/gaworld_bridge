from main import can_redeem


def test_below_v2_threshold():
    assert can_redeem(149) is False


def test_at_v2_threshold():
    assert can_redeem(150) is True


def test_v1_near_miss_now_allowed():
    assert can_redeem(199) is True
