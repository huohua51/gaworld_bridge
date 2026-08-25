from main import route


def test_closed_center_never_selected():
    assert route(9, True) is None
    assert route(1, True) is None


def test_v2_threshold():
    assert route(6, False) == "emergency"
    assert route(7, False) == "emergency"
    assert route(5, False) == "standard"
