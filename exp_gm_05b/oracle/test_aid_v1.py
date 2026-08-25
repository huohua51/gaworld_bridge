from main import eligible


def test_age_gate():
    assert eligible(17, 10000) is False
    assert eligible(18, 10000) is True


def test_v1_cap_inclusive():
    assert eligible(30, 50000) is True
    assert eligible(30, 50001) is False


def test_v1_allows_45001():
    assert eligible(30, 45001) is True
