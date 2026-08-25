from main import eligible


def test_yes_at_threshold():
    assert eligible(18) == "yes"


def test_no_below():
    assert eligible(17) == "no"


def test_yes_above():
    assert eligible(30) == "yes"
