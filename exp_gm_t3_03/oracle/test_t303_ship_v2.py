from main import free_shipping


def test_below_v2_threshold():
    assert free_shipping(11) is False


def test_at_v2_threshold():
    assert free_shipping(12) is True


def test_v1_cutover_now_paid():
    assert free_shipping(8) is False
