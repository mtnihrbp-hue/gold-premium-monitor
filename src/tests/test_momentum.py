"""Tests for premium momentum analysis.

Tests the label logic, verbal direction, and momentum context building.
"""

import unittest

from caluclator.momentum import _label_premium_diff, _verbal_direction, _fallback_momentum


class TestLabelPremiumDiff(unittest.TestCase):
    def test_discount_deepening(self):
        label, emoji = _label_premium_diff(-0.10)
        self.assertEqual(label, "Discount Deepening")
        self.assertEqual(emoji, "▼")

    def test_premium_expanding(self):
        label, emoji = _label_premium_diff(0.10)
        self.assertEqual(label, "Premium Expanding")
        self.assertEqual(emoji, "▲")

    def test_stable(self):
        label, emoji = _label_premium_diff(0.02)
        self.assertEqual(label, "Stable")
        self.assertEqual(emoji, "→")

    def test_stable_negative(self):
        label, emoji = _label_premium_diff(-0.02)
        self.assertEqual(label, "Stable")
        self.assertEqual(emoji, "→")

    def test_boundary_exact(self):
        label, emoji = _label_premium_diff(-0.05)
        self.assertEqual(label, "Stable")
        self.assertEqual(emoji, "→")


class TestVerbalDirection(unittest.TestCase):
    def test_toward_buy(self):
        self.assertEqual(_verbal_direction(-4.0, -0.5), "Toward Buy")

    def test_toward_sell(self):
        self.assertEqual(_verbal_direction(2.0, 0.5), "Toward Sell")

    def test_neutral(self):
        self.assertEqual(_verbal_direction(-4.0, 0.02), "Neutral")

    def test_toward_buy_from_positive(self):
        self.assertEqual(_verbal_direction(1.0, -1.0), "Toward Buy")

    def test_toward_sell_from_negative(self):
        self.assertEqual(_verbal_direction(-3.0, 1.0), "Toward Sell")


class TestFallbackMomentum(unittest.TestCase):
    def test_returns_minimal_dict(self):
        result = _fallback_momentum(-4.10)
        self.assertIsNone(result["premium_vs_today"])
        self.assertIsNone(result["premium_vs_yesterday"])
        self.assertIsNone(result["candlestick"])
        self.assertEqual(result["verbal_direction"], "Neutral (no history)")


if __name__ == "__main__":
    unittest.main()
