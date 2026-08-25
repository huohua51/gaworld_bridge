from main import too_loud


def test_below_v2_threshold():
    assert too_loud(61) is False


def test_at_v2_threshold():
    assert too_loud(62) is True


def test_v1_near_miss_now_loud():
    assert too_loud(69) is True
