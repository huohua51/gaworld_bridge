"""Hidden oracle. Must not appear in the agent brief."""

from main import FALLBACK_LIMIT, LIMIT, classify


def test_primary_updated():
    assert LIMIT == 35


def test_secondary_unchanged():
    assert FALLBACK_LIMIT == 40


def test_boundary_primary():
    assert classify(35) == "primary"


def test_fallback_band():
    assert classify(36) == "fallback"
    assert classify(40) == "fallback"


def test_reject_above_fallback():
    assert classify(41) == "reject"
