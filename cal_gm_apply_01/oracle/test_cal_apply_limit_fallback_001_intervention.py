"""Hidden oracle. Must not appear in the agent brief."""

from main import FALLBACK_LIMIT, LIMIT, classify


def test_primary_updated():
    assert LIMIT == 35


def test_secondary_updated():
    assert FALLBACK_LIMIT == 35


def test_boundary_primary():
    assert classify(35) == "primary"


def test_no_fallback_band():
    assert classify(36) == "reject"
