"""Unit tests for trend analysis module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from caluclator.trends import (
    get_recent_trend,
    get_7day_ma,
    get_trend_summary,
)


def _make_history(premiums):
    """Build minimal history entries from a list of premium values."""
    return [
        {"premium": p, "timestamp": f"2026-08-01T{i:02d}:00:00"}
        for i, p in enumerate(premiums)
    ]


def test_recent_trend_up():
    """Arrow up when premium rises over 3 samples."""
    history = _make_history([0.0, 1.0, 2.0])
    diff, arrow = get_recent_trend(history)
    assert arrow == "↑"
    assert diff == 2.0


def test_recent_trend_down():
    """Arrow down when premium falls over 3 samples."""
    history = _make_history([2.0, 1.0, 0.0])
    diff, arrow = get_recent_trend(history)
    assert arrow == "↓"
    assert diff == -2.0


def test_recent_trend_flat():
    """Arrow flat when change is within 0.5%."""
    history = _make_history([1.0, 1.2, 1.3])
    diff, arrow = get_recent_trend(history)
    assert arrow == "→"
    assert abs(diff - 0.3) < 0.01


def test_recent_trend_exact_threshold():
    """Edge: exactly 0.5 change should be flat."""
    history = _make_history([0.0, 0.25, 0.5])
    diff, arrow = get_recent_trend(history)
    assert arrow == "→"


def test_recent_trend_insufficient_data():
    """Returns None diff and flat arrow with <3 points."""
    history = _make_history([1.0, 2.0])
    diff, arrow = get_recent_trend(history)
    assert diff is None
    assert arrow == "→"


def test_7day_ma_typical():
    """Correct average over 7 points."""
    history = _make_history([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    ma = get_7day_ma(history)
    assert ma == 4.0


def test_7day_ma_insufficient():
    """Returns None with fewer than 7 points."""
    history = _make_history([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    ma = get_7day_ma(history)
    assert ma is None


def test_7day_ma_uses_last_7():
    """Only uses the most recent 7 entries."""
    history = _make_history([100.0] * 5 + [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    ma = get_7day_ma(history)
    assert ma == 4.0


def test_trend_summary_structure():
    """get_trend_summary returns expected keys."""
    history = _make_history([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    summary = get_trend_summary(history)
    assert "arrow" in summary
    assert "arrow_diff" in summary
    assert "ma7" in summary
    assert "history_length" in summary
    assert summary["history_length"] == 8
    assert summary["ma7"] == 4.0


def test_trend_summary_empty_history():
    """Handles empty history gracefully."""
    summary = get_trend_summary([])
    assert summary["arrow"] == "→"
    assert summary["arrow_diff"] is None
    assert summary["ma7"] is None
    assert summary["history_length"] == 0


def test_backward_compat_alias():
    """get_3day_trend still works as alias."""
    from caluclator.trends import get_3day_trend
    history = _make_history([0.0, 1.0, 2.0])
    diff, arrow = get_3day_trend(history)
    assert arrow == "↑"


if __name__ == "__main__":
    test_recent_trend_up()
    test_recent_trend_down()
    test_recent_trend_flat()
    test_recent_trend_exact_threshold()
    test_recent_trend_insufficient_data()
    test_7day_ma_typical()
    test_7day_ma_insufficient()
    test_7day_ma_uses_last_7()
    test_trend_summary_structure()
    test_trend_summary_empty_history()
    test_backward_compat_alias()
    print("All trend tests passed.")
