"""Hidden oracle. Must not appear in the agent brief."""

from main import EMERGENCY_CAPACITY, NORMAL_CAPACITY, capacity


def test_normal_updated():
    assert NORMAL_CAPACITY == 60


def test_emergency_updated():
    assert EMERGENCY_CAPACITY == 60


def test_normal_call():
    assert capacity(False) == 60


def test_emergency_call():
    assert capacity(True) == 60
