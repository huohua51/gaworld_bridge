from main import battery_ok


def test_below_v2_threshold():
    assert battery_ok(34) is False


def test_at_v2_threshold():
    assert battery_ok(35) is True


def test_v1_cutover_now_low():
    assert battery_ok(20) is False
