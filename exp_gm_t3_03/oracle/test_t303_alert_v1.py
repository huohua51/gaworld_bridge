from main import should_alert


def test_below_v1_threshold():
    assert should_alert(37) is False


def test_at_v1_threshold():
    assert should_alert(38) is True


def test_v2_cutover_still_quiet():
    assert should_alert(36) is False
