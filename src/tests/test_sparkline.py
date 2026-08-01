"""Unit tests for ASCII sparkline generator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from caluclator.sparkline import sparkline, premium_sparkline


def test_sparkline_basic():
    """Generates non-empty string for valid data."""
    result = sparkline([1, 2, 3, 4, 5])
    assert len(result) == 5
    assert all(c in "▁▂▃▄▅▆▇█" for c in result)


def test_sparkline_ascending():
    """Ascending values should produce ascending blocks."""
    result = sparkline([1, 2, 3, 4, 5, 6, 7, 8])
    # First should be lowest block, last should be highest
    assert result[0] < result[-1]


def test_sparkline_descending():
    """Descending values should produce descending blocks."""
    result = sparkline([8, 7, 6, 5, 4, 3, 2, 1])
    assert result[0] > result[-1]


def test_sparkline_flat():
    """Flat values produce flat line."""
    result = sparkline([5, 5, 5, 5])
    assert result == "────"


def test_sparkline_empty():
    """Empty list returns empty string."""
    assert sparkline([]) == ""


def test_sparkline_single():
    """Single value returns empty string (need 2+ for shape)."""
    assert sparkline([5]) == ""


def test_sparkline_width_limit():
    """Respects width parameter."""
    values = list(range(50))
    result = sparkline(values, width=10)
    assert len(result) == 10


def test_sparkline_negative_values():
    """Handles negative values correctly."""
    result = sparkline([-5, -3, 0, 3, 5])
    assert len(result) == 5
    assert all(c in "▁▂▃▄▅▆▇█─" for c in result)


def test_premium_sparkline_from_history():
    """Convenience function works with history format."""
    history = [
        {"premium": 1.0},
        {"premium": 2.0},
        {"premium": 3.0},
    ]
    result = premium_sparkline(history)
    assert len(result) == 3


def test_premium_sparkline_empty_history():
    """Empty history returns empty string."""
    assert premium_sparkline([]) == ""


if __name__ == "__main__":
    test_sparkline_basic()
    test_sparkline_ascending()
    test_sparkline_descending()
    test_sparkline_flat()
    test_sparkline_empty()
    test_sparkline_single()
    test_sparkline_width_limit()
    test_sparkline_negative_values()
    test_premium_sparkline_from_history()
    test_premium_sparkline_empty_history()
    print("All sparkline tests passed.")
