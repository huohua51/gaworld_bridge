from main import battery_ok


def test_below_v1_threshold():
    assert battery_ok(19) is False


def test_at_v1_threshold():
    assert battery_ok(20) is True


def test_mid_level_still_ok():
    assert battery_ok(34) is True
