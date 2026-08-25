from main import remaining


def test_positive():
    assert remaining(40) == 60


def test_exact():
    assert remaining(100) == 0


def test_overspend():
    assert remaining(150) == 0
