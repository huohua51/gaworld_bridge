from main import should_alert


def test_below_v2_threshold():
    assert should_alert(35) is False


def test_at_v2_threshold():
    assert should_alert(36) is True


def test_v1_near_miss_now_alerts():
    assert should_alert(37) is True
