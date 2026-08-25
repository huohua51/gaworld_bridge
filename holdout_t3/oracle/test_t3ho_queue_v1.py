from main import queue_full


def test_below_v1_threshold():
    assert queue_full(14) is False


def test_at_v1_threshold():
    assert queue_full(15) is True


def test_v2_cutover_still_open():
    assert queue_full(11) is False
