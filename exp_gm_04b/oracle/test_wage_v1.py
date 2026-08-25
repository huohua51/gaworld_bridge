from main import decide


def test_accept_at_threshold():
    assert decide(60000) == "accept"


def test_reject_below():
    assert decide(59999) == "reject"


def test_accept_above_old_and_new():
    assert decide(70000) == "accept"
