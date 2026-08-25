"""Hidden oracle. Must not appear in the agent brief."""

from main import WEEKDAY_DEADLINE, WEEKEND_DEADLINE, deadline


def test_weekday_updated():
    assert WEEKDAY_DEADLINE == 20


def test_weekend_unchanged():
    assert WEEKEND_DEADLINE == 30


def test_weekday_call():
    assert deadline(False) == 20


def test_weekend_call():
    assert deadline(True) == 30
