from main import too_loud


def test_below_v1_threshold():
    assert too_loud(69) is False


def test_at_v1_threshold():
    assert too_loud(70) is True


def test_v2_cutover_still_quiet():
    assert too_loud(62) is False
