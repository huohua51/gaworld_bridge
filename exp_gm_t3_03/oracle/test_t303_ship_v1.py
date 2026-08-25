from main import free_shipping


def test_below_v1_threshold():
    assert free_shipping(7) is False


def test_at_v1_threshold():
    assert free_shipping(8) is True


def test_mid_weight_still_free():
    assert free_shipping(11) is True
