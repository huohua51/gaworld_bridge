from main import queue_full


def test_below_v2_threshold():
    assert queue_full(10) is False


def test_at_v2_threshold():
    assert queue_full(11) is True


def test_v1_near_miss_now_full():
    assert queue_full(14) is True
