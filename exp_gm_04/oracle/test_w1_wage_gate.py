"""Hidden oracle. Must not appear in the agent brief."""

from main import decide


def test_accept_above():
    assert decide(8000, 9000) == "accept"


def test_reject_below():
    assert decide(8000, 6500) == "reject"


def test_accept_equal_boundary():
    assert decide(8000, 8000) == "accept"


def test_float_inputs():
    assert decide(8000.0, 7999.9) == "reject"
