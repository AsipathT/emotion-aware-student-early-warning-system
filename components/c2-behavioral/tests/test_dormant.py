"""
Unit tests for causal dormancy detection rule.
"""

from src.dormant import causal_dormancy


def test_causal_dormancy_no_activity_7w():
    """[5,0,0,0,0,0,0,0] -> 'no_activity_7w' (clicks earlier, last 7 weeks zero)."""
    assert causal_dormancy([5, 0, 0, 0, 0, 0, 0, 0]) == "no_activity_7w"


def test_causal_dormancy_never_active():
    """[0]*7 -> 'never_active' (all 7 weeks zero, no earlier clicks)."""
    assert causal_dormancy([0] * 7) == "never_active"


def test_causal_dormancy_under_7_weeks():
    """[0]*6 -> None (fewer than 7 weeks)."""
    assert causal_dormancy([0] * 6) is None


def test_causal_dormancy_only_6_zeros():
    """[5,0,0,0,0,0,0] -> None (only 6 zeros)."""
    assert causal_dormancy([5, 0, 0, 0, 0, 0, 0]) is None


def test_causal_dormancy_active_at_t():
    """[0,0,0,0,0,0,0,3] -> None (active at week t)."""
    assert causal_dormancy([0, 0, 0, 0, 0, 0, 0, 3]) is None
