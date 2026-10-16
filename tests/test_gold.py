"""Unit tests for gold fair-price calculator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from caluclator.gold import (
    calculate_fair_price,
    find_lowest_market_price,
    premium_percent,
    trading_signal,
)


def test_calculate_fair_price_typical():
    """Fair price for typical values."""
    # $2000/oz, 50000 IRR/USD
    # 2000 * 50000 / 31.1034768 * 0.750 = ~2,411,000 IRR per gram pure-ish
    result = calculate_fair_price(2000.0, 50000.0)
    expected = 2000.0 * 50000.0 / 31.1034768 * 0.750
    assert abs(result - expected) < 0.01


def test_calculate_fair_price_zero_world():
    """Zero world price returns 0."""
    result = calculate_fair_price(0.0, 50000.0)
    assert result == 0.0


def test_find_lowest_single():
    """Lowest of single valid price."""
    prices = {"Milli": {"price": 2500000.0, "status": "OK"}}
    assert find_lowest_market_price(prices) == 2500000.0


def test_find_lowest_multiple():
    """Lowest of multiple prices."""
    prices = {
        "Milli": {"price": 2500000.0, "status": "OK"},
        "Goldika": {"price": 2400000.0, "status": "OK"},
        "WallGold": {"price": 2600000.0, "status": "OK"},
    }
    assert find_lowest_market_price(prices) == 2400000.0


def test_find_lowest_all_errors():
    """None when all sources error."""
    prices = {
        "Milli": {"price": None, "status": "ERROR: timeout"},
        "Goldika": {"price": None, "status": "ERROR: timeout"},
    }
    assert find_lowest_market_price(prices) is None


def test_find_lowest_mixed():
    """Ignores errors, picks lowest valid."""
    prices = {
        "Milli": {"price": 2500000.0, "status": "OK"},
        "Goldika": {"price": None, "status": "ERROR"},
        "WallGold": {"price": 2400000.0, "status": "OK"},
    }
    assert find_lowest_market_price(prices) == 2400000.0


def test_premium_percent_typical():
    """Premium for price above fair."""
    # fair=2_000_000, market=2_100_000 → 5%
    result = premium_percent(2_000_000.0, 2_100_000.0)
    assert abs(result - 5.0) < 0.01


def test_premium_percent_discount():
    """Discount (negative premium)."""
    result = premium_percent(2_000_000.0, 1_900_000.0)
    assert abs(result - (-5.0)) < 0.01


def test_premium_percent_zero_fair():
    """Zero fair price returns 0 to avoid division by zero."""
    result = premium_percent(0.0, 2_000_000.0)
    assert result == 0.0


def test_trading_signal_buy():
    assert trading_signal(-2.0, -1.5, 3.0) == "BUY"


def test_trading_signal_sell():
    assert trading_signal(4.0, -1.5, 3.0) == "SELL"


def test_trading_signal_hold():
    assert trading_signal(0.0, -1.5, 3.0) == "HOLD"


def test_trading_signal_exact_buy_threshold():
    assert trading_signal(-1.5, -1.5, 3.0) == "BUY"


def test_trading_signal_exact_sell_threshold():
    assert trading_signal(3.0, -1.5, 3.0) == "SELL"


if __name__ == "__main__":
    test_calculate_fair_price_typical()
    test_calculate_fair_price_zero_world()
    test_find_lowest_single()
    test_find_lowest_multiple()
    test_find_lowest_all_errors()
    test_find_lowest_mixed()
    test_premium_percent_typical()
    test_premium_percent_discount()
    test_premium_percent_zero_fair()
    test_trading_signal_buy()
    test_trading_signal_sell()
    test_trading_signal_hold()
    test_trading_signal_exact_buy_threshold()
    test_trading_signal_exact_sell_threshold()
    print("All gold calculator tests passed.")
