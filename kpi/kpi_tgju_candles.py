"""KPI -- tgju daily candles, collected and stored (SP-D TA track, step 1).

Technical analysis needs real candles and a long history. Our platform_candles are
single points (98% have open = high = low = close) and our own daily candles go back
15 days. tgju.org's history pages publish daily candles for 18K gold from 2013 and the
dollar from 2011, and tgju's 18K daily close tracks our platforms at 0.95 daily
correlation (SP_C_HANDOFF.md section 41).

The 11:00 and 12:00 runs of 2026-09-30 proved the production runner collects them in
log-only mode. Since section 41.6 every scheduled run stores them in
market_daily_candles: the history a page per run, oldest first (section 43), then
each new completed day.

Load-bearing properties:
- the columns are read in tgju's order: open, low, high, close;
- one instrument failing does not stop the other, in collection or in storage;
- a hung request cannot hold a run: one shared deadline bounds the collection;
- the collection never raises into main, and runs on scheduled runs only;
- an instrument whose history is missing pages through it oldest first, resuming
  from its stored count, and only that instrument does;
- only completed Tehran days are stored, never today's;
- tgju is asked about once a day: not while the last trading day is stored;
- a second run stores nothing twice, and first-seen values are never overwritten;
- a candle whose low and high do not bound it is kept as published, flagged;
- the collector itself stores nothing: collectors collect, main stores.

No test here reaches the network: requests.get is substituted (kpi_coherence.test_27).
"""

import contextlib
import inspect
import io
import os
import sys
import time
import unittest
from datetime import date, datetime

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import collector.tgju as tgju
import main
from database.connection import Base
from database.models import MarketDailyCandle

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

# 12:00 Tehran on Wednesday 2026-09-30, and on the Thursday after.
NOW = datetime(2026, 9, 30, 8, 30)
NEXT_DAY = datetime(2026, 10, 1, 8, 30)


def _row(day, open_, low, high, close):
    return [f"{open_:,}", f"{low:,}", f"{high:,}", f"{close:,}", "0", "0%", day, ""]


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

    def rows_requested(self):
        return {url.rsplit("/", 1)[-1]: kwargs["params"]["length"] for url, kwargs in self.calls}

    def plans(self):
        return {url.rsplit("/", 1)[-1]: (kwargs["params"]["start"], kwargs["params"]["length"],
                                         kwargs["params"]["order_dir"])
                for url, kwargs in self.calls}


class KPITgjuCandles(unittest.TestCase):

    def setUp(self):
        self.original_get_session = main.get_session
        self._fresh_database()

    def tearDown(self):
        main.get_session = self.original_get_session

    def _fresh_database(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)
        main.get_session = self.Session

    def _run(self, fake, now=NOW):
        """One scheduled collection against `fake`; returns (transport, printed)."""
        out = io.StringIO()
        with _Transport(fake) as transport, contextlib.redirect_stdout(out):
            main._collect_tgju_candles(now=now)
        return transport, out.getvalue()

    def _stored(self, instrument="TGJU_GOLD_18K"):
        session = self.Session()
        try:
            return {row.trade_date: row for row in session.query(MarketDailyCandle)
                    .filter(MarketDailyCandle.instrument == instrument)}
        finally:
            session.close()

    # -- collection ------------------------------------------------------------

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

    def test_06_the_collection_never_raises_into_main(self):
        def broken(**kwargs):
            raise RuntimeError("collector exploded")

        original = tgju.collect_daily_candles
        tgju.collect_daily_candles = broken
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                main._collect_tgju_candles(now=NOW)          # must not raise
        finally:
            tgju.collect_daily_candles = original

        def no_database():
            raise RuntimeError("database unreachable")

        main.get_session = no_database
        with contextlib.redirect_stdout(io.StringIO()):
            main._collect_tgju_candles(now=NOW)              # must not raise either

    def test_07_the_collection_runs_on_scheduled_runs_only(self):
        source = inspect.getsource(main.main)
        news = source.index("news_result = run_news_ingestion(config)")
        collection = source.index("_collect_tgju_candles()")
        analysis = source.index("analysis_snapshot_id = build_analysis_snapshot")
        self.assertLess(news, collection)
        self.assertLess(collection, analysis, "the collection left the scheduled block")
        self.assertEqual(source.count("_collect_tgju_candles()"), 1)

    # -- storage ---------------------------------------------------------------

    def test_08_a_missing_history_is_asked_for_a_page_at_a_time(self):
        """The whole history in one request failed from the runner at 14:00 on
        2026-09-30: tgju's answer time follows its load (section 43)."""
        today = date(2026, 9, 30)
        page, window = main.TGJU_BACKFILL_PAGE_ROWS, main.TGJU_WINDOW_ROWS
        self.assertEqual(main._tgju_requests({}, today),
                         {"geram18": (0, page, "asc"), "price_dollar_rl": (0, page, "asc"),
                          "ons": (0, page, "asc")})
        needed = main._tgju_requests({"TGJU_GOLD_18K": (3516, date(2026, 9, 29))}, today)
        self.assertEqual(needed, {"geram18": (0, window, "desc"),
                                  "price_dollar_rl": (0, page, "asc"), "ons": (0, page, "asc")},
                         "a missing dollar history made gold page through its own again")
        needed = main._tgju_requests({"TGJU_GOLD_18K": (1000, date(2017, 8, 4))}, today)
        self.assertEqual(needed["geram18"], (1000, page, "asc"),
                         "a part-filled history must resume from its stored count")
        needed = main._tgju_requests({"TGJU_GOLD_18K": (3500, date(2026, 8, 31))}, today)
        self.assertEqual(needed["geram18"], (0, 35, "desc"),
                         "a 30-day gap must be reached back over")

        transport, _ = self._run(lambda url, **kw: _Response(PAYLOAD))
        self.assertEqual(transport.plans(), {"geram18": (0, page, "asc"),
                                             "price_dollar_rl": (0, page, "asc"),
                                             "ons": (0, page, "asc")})

    def test_09_completed_days_are_stored_and_today_is_not(self):
        payload = {"data": [_row("2026/09/30", 250, 249, 252, 251),
                            _row("2026/09/29", 244, 243, 253, 252),
                            _row("2026/09/28", 239, 238, 246, 244)]}
        self._run(lambda url, **kw: _Response(payload))
        self.assertEqual(set(self._stored()), {date(2026, 9, 29), date(2026, 9, 28)})

        # 00:30 Tehran on the 30th is still the 29th in UTC: the 29th is complete.
        self._fresh_database()
        self._run(lambda url, **kw: _Response(payload), now=datetime(2026, 9, 29, 21, 0))
        self.assertIn(date(2026, 9, 29), self._stored(),
                      "the day was cut at UTC midnight, not Tehran's")

    def test_10_a_second_run_stores_nothing_twice(self):
        self._run(lambda url, **kw: _Response(PAYLOAD))
        # The next day, before tgju has published the 30th: the window is re-read.
        transport, printed = self._run(lambda url, **kw: _Response(PAYLOAD), now=NEXT_DAY)
        self.assertEqual(len(self._stored()), 2)
        self.assertEqual(len(self._stored("TGJU_USD_IRR")), 2)
        self.assertIn("geram18: 0 new", printed)
        self.assertEqual(set(transport.rows_requested().values()), {main.TGJU_WINDOW_ROWS},
                         "a run with history stored fetched it again")

    def test_11_first_seen_values_are_never_overwritten(self):
        self._run(lambda url, **kw: _Response(PAYLOAD))
        changed = {"data": [_row("2026/09/29", 244_014_000, 244_014_000, 253_017_000, 252_000_000),
                            PAYLOAD["data"][1]]}
        _, printed = self._run(lambda url, **kw: _Response(changed), now=NEXT_DAY)
        self.assertEqual(float(self._stored()[date(2026, 9, 29)].close), 252_655_000.0)
        self.assertIn("changed by tgju since stored", printed)
        self.assertIn("2026-09-29", printed)

    def test_12_an_inconsistent_candle_is_kept_flagged_and_an_invalid_one_is_not(self):
        # The shape tgju published on 2025-09-25: a low above the high, at a cap.
        payload = {"data": [_row("2026/09/29", 99_462_000, 100_000_000, 99_997_000, 99_757_000),
                            _row("2026/09/28", 239, 238, 246, 244),
                            _row("2026/09/27", 0, 0, 0, 0)]}
        _, printed = self._run(lambda url, **kw: _Response(payload))
        stored = self._stored()
        self.assertEqual(stored[date(2026, 9, 29)].source_quality, "INCONSISTENT")
        self.assertEqual(float(stored[date(2026, 9, 29)].low), 100_000_000.0,
                         "a flagged candle must be kept as published, not corrected")
        self.assertEqual(stored[date(2026, 9, 28)].source_quality, "COMPLETE")
        self.assertNotIn(date(2026, 9, 27), stored)
        self.assertIn("without a valid price skipped", printed)

    def test_13_one_instrument_failing_does_not_stop_the_other_being_stored(self):
        def fake(url, **kw):
            if "price_dollar_rl" in url:
                return _Response({}, status=503)
            return _Response(PAYLOAD)

        _, printed = self._run(fake)
        self.assertEqual(len(self._stored()), 2)
        self.assertEqual(self._stored("TGJU_USD_IRR"), {})
        self.assertIn("price_dollar_rl: ERROR", printed)

        # The next run pages the dollar from its start, and gives gold a window.
        transport, _ = self._run(lambda url, **kw: _Response(PAYLOAD), now=NEXT_DAY)
        self.assertEqual(transport.plans(),
                         {"geram18": (0, main.TGJU_WINDOW_ROWS, "desc"),
                          "price_dollar_rl": (0, main.TGJU_BACKFILL_PAGE_ROWS, "asc"),
                          "ons": (0, main.TGJU_WINDOW_ROWS, "desc")})

    def test_14_provenance_is_recorded_and_the_collector_stores_nothing(self):
        self._run(lambda url, **kw: _Response(PAYLOAD))
        row = self._stored()[date(2026, 9, 29)]
        self.assertEqual((row.source, row.unit, row.trade_date_jalali),
                         ("tgju", "IRR", "1405/07/07"))
        self.assertEqual(self._stored("TGJU_XAU_USD")[date(2026, 9, 29)].unit, "USD",
                         "world gold is in dollars per ounce, not Rial")
        self.assertEqual(row.collected_at, NOW, "collected_at must be the run's UTC time")

        module_source = inspect.getsource(tgju)
        for storage in ("database", "save_", "session", "INSERT"):
            self.assertNotIn(storage, module_source, "collectors collect; main stores")

    def test_15_tgju_is_asked_about_once_a_day(self):
        """Section 41.5 committed the stored collection to once a day, not two requests
        an hour: a run whose table already holds the last trading day asks nothing."""
        self._run(lambda url, **kw: _Response(PAYLOAD))
        transport, printed = self._run(lambda url, **kw: _Response(PAYLOAD))
        self.assertEqual(transport.calls, [], "an up-to-date table still asked tgju")
        self.assertIn("up to date", printed)

        # Saturday 2026-10-03: Iran has no Friday candle, so Thursday's is the newest
        # there is; world gold trades Friday and not at the weekend.
        last = main._tgju_last_trading_day
        self.assertEqual(last(date(2026, 10, 3)), date(2026, 10, 1))
        self.assertEqual(last(date(2026, 10, 1)), date(2026, 9, 30))
        self.assertEqual(last(date(2026, 10, 3), "ons"), date(2026, 10, 2))
        self.assertEqual(last(date(2026, 10, 5), "ons"), date(2026, 10, 2), "Monday: Friday's")
        self.assertEqual(last(date(2026, 10, 4), "ons"), date(2026, 10, 2), "Sunday: Friday's")

        def market(url, **kw):
            if url.endswith("/ons"):
                return _Response({"data": [_row("2026/10/02", 4170, 4120, 4220, 4140),
                                           _row("2026/10/01", 4150, 4140, 4190, 4175)]})
            return _Response({"data": [_row("2026/10/01", 250, 249, 252, 251)]})

        self._run(market, now=datetime(2026, 10, 3, 8, 30))
        transport, _ = self._run(market, now=datetime(2026, 10, 3, 9, 30))
        self.assertEqual(transport.calls, [], "a Saturday kept asking for a candle no market made")

        # A day behind: asked again.
        transport, _ = self._run(market, now=datetime(2026, 10, 4, 8, 30))
        self.assertTrue(transport.calls)


    def test_16_a_history_is_filled_page_by_page_without_gaps_or_repeats(self):
        """A fake tgju with 2,500 days that honours start, length and order, and
        answers past the end as the real one does, with a body that is not JSON."""
        from datetime import timedelta
        last = date(2026, 9, 29)
        days = [last - timedelta(days=2499 - i) for i in range(2500)]     # oldest first

        class _NotJson(_Response):
            def json(self):
                raise ValueError("Expecting value: line 1 column 1 (char 0)")

        def server(url, **kw):
            p = kw["params"]
            ordered = days if p["order_dir"] == "asc" else days[::-1]
            if p["start"] >= len(ordered):
                return _NotJson(None)
            page = ordered[p["start"]:p["start"] + p["length"]]
            return _Response({"recordsTotal": len(days), "data": [
                _row(d.strftime("%Y/%m/%d"), 100 + i, 99 + i, 102 + i, 101 + i)
                for i, d in enumerate(page)]})

        plans = []
        for _ in range(3):
            transport, printed = self._run(server)
            plans.append(transport.plans()["geram18"])
        page = main.TGJU_BACKFILL_PAGE_ROWS
        self.assertEqual(plans, [(0, page, "asc"), (page, page, "asc"), (2 * page, page, "asc")])
        self.assertIn("history page from row 2000", printed)
        for instrument in ("TGJU_GOLD_18K", "TGJU_USD_IRR", "TGJU_XAU_USD"):
            self.assertEqual(sorted(self._stored(instrument)), days,
                             f"{instrument}: the pages left a gap or a repeat")

        transport, printed = self._run(server)
        self.assertEqual(transport.calls, [], "a complete history kept paging")
        self.assertIn("up to date", printed)

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
