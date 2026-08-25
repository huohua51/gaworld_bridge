from main import min_return


def test_rate_on_100():
    assert min_return(100) == 50


def test_zero_principal():
    assert min_return(0) == 0


def test_integer():
    assert isinstance(min_return(10), int)
