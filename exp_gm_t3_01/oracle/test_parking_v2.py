from main import fee_required


def test_below_v2_threshold():
    assert fee_required(89) is False


def test_at_v2_threshold():
    assert fee_required(90) is True


def test_v1_cutover_now_charged():
    assert fee_required(119) is True
