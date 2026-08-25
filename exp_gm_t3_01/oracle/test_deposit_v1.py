from main import deposit


def test_hundred():
    assert deposit(100) == 20


def test_fifty():
    assert deposit(50) == 10


def test_not_v2_rate():
    assert deposit(100) != 30
