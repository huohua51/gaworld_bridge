from main import decide


def test_reject_old_threshold():
    assert decide(60000) == "reject"


def test_reject_just_below_new():
    assert decide(69999) == "reject"


def test_accept_at_new_threshold():
    assert decide(70000) == "accept"
