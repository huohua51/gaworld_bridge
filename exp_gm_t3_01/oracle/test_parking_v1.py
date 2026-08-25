from main import fee_required


def test_below_v1_threshold():
    assert fee_required(119) is False


def test_at_v1_threshold():
    assert fee_required(120) is True


def test_v2_cutover_still_free():
    assert fee_required(90) is False
