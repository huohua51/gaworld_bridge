from main import remaining


def test_positive():
    assert remaining(30) == 50


def test_exact():
    assert remaining(80) == 0


def test_old_budget_overspend():
    assert remaining(90) == 0
