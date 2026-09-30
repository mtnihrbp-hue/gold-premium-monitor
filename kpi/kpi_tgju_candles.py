"""KPI -- tgju daily candles, collected in log-only mode (SP-D TA track, step 1).

Technical analysis needs real candles and a long history. Our platform_candles are
single points (98% have open = high = low = close) and our own daily candles go back
15 days. tgju.org's history pages publish daily candles for 18K gold from 2013 and the
dollar from 2011, and tgju's 18K daily close tracks our platforms at 0.95 daily
correlation (SP_C_HANDOFF.md section 41).

This step only proves the production runner can collect them. The run prints the latest
candles and stores nothing until a table is migrated for them.

Load-bearing properties:
- the columns are read in tgju's order: open, low, high, close;
- one instrument failing does not stop the other;
- a hung request cannot hold a run: one shared deadline bounds the collection;
- the probe never raises into main, and runs on scheduled runs only;
- nothing is stored.

No test here reaches the network: requests.get is substituted (kpi_coherence.test_27).
"""

import inspect
import os
import sys
import time
import unittest

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

import collector.tgju as tgju

# Two rows as the endpoint returned them on 2026-09-30.
PAYLOAD = {
    "draw": 0, "recordsTotal": 3516, "recordsFiltered": 3516,
    "data": [
        ["244,014,000", "244,014,000", "253,017,000", "252,655,000", "8643000", "3.54%",
         "2026/09/29", "1405/07/07"],
        ["<span>239,030,000</span>", "239,030,000", "245,868,000", "244,012,000", "4996000",
         "2.09%", "2026/09/28", "1405/07/06"],
    ],
}


class _Response:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Transport:
    """Substitutes requests.get for the duration of a test."""

    def __init__(self, fake):
        self.fake, self.calls = fake, []

    def __enter__(self):
        self.original = tgju.requests.get

        def get(url, **kwargs):
            self.calls.append((url, kwargs))
            return self.fake(url, **kwargs)

        tgju.requests.get = get
        return self

    def __exit__(self, *exc):
        tgju.requests.get = self.original


class KPITgjuCandles(unittest.TestCase):

    def test_01_columns_are_open_low_high_close(self):
        candles = tgju.parse_rows(PAYLOAD)
        latest = candles[0]
        self.assertEqual(latest["date"], "2026-09-29")
        self.assertEqual(latest["jdate"], "1405/07/07")
        self.assertEqual((latest["open"], latest["low"], latest["high"], latest["close"]),
                         (244_014_000.0, 244_014_000.0, 253_017_000.0, 252_655_000.0))
        self.assertEqual(candles[1]["open"], 239_030_000.0, "markup must be stripped")

    def test_02_only_the_latest_rows_are_requested(self):
        with _Transport(lambda url, **kw: _Response(PAYLOAD)) as transport:
            tgju.fetch_daily_candles("geram18", rows=2)
        url, kwargs = transport.calls[0]
        self.assertIn("summary-table-data/geram18", url)
        self.assertEqual(kwargs["params"]["length"], 2)
        self.assertEqual(kwargs["params"]["order_dir"], "desc")
        self.assertEqual(kwargs["timeout"], tgju.REQUEST_TIMEOUT)

    def test_03_an_empty_answer_is_an_error_not_a_candle(self):
        with _Transport(lambda url, **kw: _Response({"data": []})):
            self.assertRaises(ValueError, tgju.fetch_daily_candles, "geram18")

    def test_04_one_instrument_failing_does_not_stop_the_other(self):
        def fake(url, **kw):
            if "price_dollar_rl" in url:
                return _Response({}, status=503)
            return _Response(PAYLOAD)

        with _Transport(fake):
            results = tgju.collect_daily_candles(rows=2)
        self.assertEqual(results["geram18"]["status"], "OK")
        self.assertTrue(results["price_dollar_rl"]["status"].startswith("ERROR"))

    def test_05_a_hung_request_cannot_hold_the_run(self):
        def hang(url, **kw):
            time.sleep(3)
            return _Response(PAYLOAD)

        original = tgju.DEADLINE_SECONDS
        tgju.DEADLINE_SECONDS = 0.5
        try:
            with _Transport(hang):
                started = time.monotonic()
                results = tgju.collect_daily_candles()
                elapsed = time.monotonic() - started
        finally:
            tgju.DEADLINE_SECONDS = original
        self.assertLess(elapsed, 1.5, "the collection waited past its deadline")
        self.assertEqual({r["status"] for r in results.values()}, {"TIMEOUT"})

    def test_06_the_probe_never_raises_into_main(self):
        import main

        def broken(**kwargs):
            raise RuntimeError("collector exploded")

        original = tgju.collect_daily_candles
        tgju.collect_daily_candles = broken
        try:
            main._log_tgju_candles()          # must not raise
        finally:
            tgju.collect_daily_candles = original

    def test_07_the_probe_runs_on_scheduled_runs_only(self):
        import main
        source = inspect.getsource(main.main)
        news = source.index("news_result = run_news_ingestion(config)")
        probe = source.index("_log_tgju_candles()")
        analysis = source.index("analysis_snapshot_id = build_analysis_snapshot")
        self.assertLess(news, probe)
        self.assertLess(probe, analysis, "the probe left the scheduled block")
        self.assertEqual(source.count("_log_tgju_candles()"), 1)

    def test_08_nothing_is_stored(self):
        """Log-only until a table is migrated for tgju's candles."""
        import main
        for module_source in (inspect.getsource(tgju), inspect.getsource(main._log_tgju_candles)):
            for storage in ("database", "save_", "session", "INSERT"):
                self.assertNotIn(storage, module_source)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(KPITgjuCandles)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print()
    print("=" * 55)
    print(f"TGJU CANDLES KPI RESULT: {passed}/{total} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
