from main import eligible


def test_no_old_threshold():
    assert eligible(18) == "no"


def test_no_just_below_new():
    assert eligible(20) == "no"


def test_yes_at_new_threshold():
    assert eligible(21) == "yes"
