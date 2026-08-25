"""Hidden oracle. Must not appear in the agent brief."""

from main import min_return


def test_rate_one_returns_principal():
    assert min_return(10, 1.0) == 10


def test_rate_zero_allows_zero():
    assert min_return(10, 0.0) == 0


def test_half_rate():
    assert min_return(20, 0.5) == 10


def test_integer_output():
    assert isinstance(min_return(10, 1.0), int)
