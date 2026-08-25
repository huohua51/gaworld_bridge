from main import can_redeem


def test_below_v1_threshold():
    assert can_redeem(199) is False


def test_at_v1_threshold():
    assert can_redeem(200) is True


def test_v2_cutover_still_blocked():
    assert can_redeem(150) is False
