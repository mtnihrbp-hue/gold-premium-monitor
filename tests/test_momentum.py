"""Tests for premium momentum analysis."""

import sys

sys.path.insert(0, "src")

import unittest

from caluclator.momentum import _fallback_momentum


class TestFallbackMomentum(unittest.TestCase):
    def test_returns_minimal_dict(self):
        result = _fallback_momentum(-4.10)
        self.assertIsNone(result["premium_vs_today"])
        self.assertIsNone(result["premium_vs_yesterday"])
        self.assertIsNone(result["candlestick"])
        self.assertEqual(result["verbal_direction"], "Neutral (no history)")


if __name__ == "__main__":
    unittest.main()
