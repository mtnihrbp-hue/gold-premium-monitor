"""Focused KPI checks for UPDATE v1 presentation primitives.

These tests are intentionally DB-independent. They verify the deterministic
classification contract without claiming empirical calibration.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from alerts.helpers import classify_candle, build_update_interpretation, bubble_state_short
from update.baseline_resolver import (
    _classify_bubble_movement,
    _classify_price_direction,
)


class KPIUpdateTelegramV1(unittest.TestCase):
    def test_01_negative_bubble(self):
        self.assertEqual(bubble_state_short(-4.0), "NEGATIVE")
        self.assertEqual(bubble_state_short(3.0), "POSITIVE")

    def test_02_bubble_increasing_decreasing_stable(self):
        self.assertEqual(_classify_bubble_movement(-4.2, -4.0)[0], "INCREASING")
        self.assertEqual(_classify_bubble_movement(-3.8, -4.0)[0], "DECREASING")
        self.assertEqual(_classify_bubble_movement(-4.02, -4.0)[0], "STABLE")

    def test_03_price_direction(self):
        self.assertEqual(_classify_price_direction(223_200_000, 223_000_000)[0], "RISING")
        self.assertEqual(_classify_price_direction(222_800_000, 223_000_000)[0], "FALLING")
        self.assertEqual(_classify_price_direction(223_010_000, 223_000_000)[0], "STABLE")

    def test_04_candle(self):
        self.assertEqual(classify_candle({"candlestick": {"open": -5.0, "close": -4.0}}), "BULLISH")
        self.assertEqual(classify_candle({"candlestick": {"open": -4.0, "close": -5.0}}), "BEARISH")
        self.assertEqual(classify_candle({"candlestick": {"open": -4.0, "close": -3.98}}), "NEUTRAL")
        self.assertEqual(classify_candle(None), "N/A")

    def test_05_interpretation(self):
        text = build_update_interpretation("RISING", "NEGATIVE", "INCREASING")
        self.assertIn("Local prices are rising", text)
        self.assertIn("negative bubble is increasing", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
