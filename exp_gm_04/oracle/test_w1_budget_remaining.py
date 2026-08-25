"""Hidden oracle. Must not appear in the agent brief."""

from main import remaining


def test_positive_remainder():
    assert remaining(100, 40) == 60


def test_exact_zero():
    assert remaining(100, 100) == 0


def test_never_negative():
    assert remaining(100, 150) == 0


def test_zero_budget():
    assert remaining(0, 1) == 0
