from main import deposit


def test_hundred():
    assert deposit(100) == 30


def test_fifty():
    assert deposit(50) == 15


def test_not_v1_rate():
    assert deposit(100) != 20
