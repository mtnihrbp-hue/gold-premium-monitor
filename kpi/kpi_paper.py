"""KPI -- SP-D PAPER portfolio: the owner's contract, held in code and in the database.

The owner's scenario (2026-10-04): the analyst trades a hypothetical 100,000,000 toman in
whole grams of 18K, at most once a day at any run, reports at 21:00 and is reviewed per
Persian quarter. The load-bearing properties are the contract's clauses:

- whole grams only, the residue stays as cash; no borrowing, no short selling;
- at most one trade per account per Tehran day, held by the engine AND by the database;
- no trade without a fresh venue price with both sides;
- one report per day from 21:00, valued at the venue's sell price, against the
  quarter's first day; quarters are Persian seasons;
- every analyst run is logged with its inputs, UNDECIDED where the signals conflict;
- messages are labelled PAPER, keep the vocabulary and are Telegram-safe;
- the account never decides for the system: it reads final_decision, never makes one.
"""

import inspect
import math
import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

from analysis import paper as p
import timeutil as t

BANNED = ("widening", "widened", "narrowing", "grew", "smaller", "falling", "dearer", "dearest",
          "deepening", "cheap")
BUY, SELL = 266_035_936.0, 259_726_784.0          # Goldika, 2026-10-04 10:35 (rial)


def _markets(buy=BUY, sell=SELL, status="OK"):
    return {"Goldika": {"price": buy, "buy": buy, "sell": sell, "status": status},
            "Milli": {"price": buy * 0.98, "status": "OK"}}


def _uptrend(n=320):
    return [150_000_000 * 1.003 ** k for k in range(n)]


class _State:
    final_decision, valuation, candidate_decision = "WAIT", "FAIR", "WAIT"


class KPIPaper(unittest.TestCase):

    # -- the Persian calendar -----------------------------------------------------------

    def test_01_jalali_dates_match_tgju(self):
        # each pair as tgju publishes it beside its daily candles (13,549 pairs checked
        # 1979-2026, 0 mismatches), including the leap years' Esfand 30
        pairs = {"1979-12-26": (1358, 10, 5), "2000-02-29": (1378, 12, 10), "2014-03-21": (1393, 1, 1),
                 "2017-03-20": (1395, 12, 30), "2017-03-21": (1396, 1, 1), "2024-03-19": (1402, 12, 29),
                 "2024-03-20": (1403, 1, 1), "2025-03-20": (1403, 12, 30), "2025-03-21": (1404, 1, 1),
                 "2026-03-21": (1405, 1, 1), "2026-09-23": (1405, 7, 1), "2026-10-01": (1405, 7, 9)}
        for g, j in pairs.items():
            self.assertEqual(t.to_jalali(date.fromisoformat(g)), j, g)
            self.assertEqual(t.from_jalali(*j), date.fromisoformat(g), j)

    def test_02_every_day_round_trips(self):
        day = t.from_jalali(1390, 1, 1)
        while day < t.from_jalali(1420, 1, 1):
            self.assertEqual(t.from_jalali(*t.to_jalali(day)), day)
            day += timedelta(days=1)

    def test_03_quarters_are_persian_seasons(self):
        # owner, 2026-10-04: "ends in 30 of Azar, next starts at 1st of Dey, ends 29 Esfand"
        self.assertEqual(t.persian_quarter(date(2026, 10, 4)), (date(2026, 9, 23), date(2026, 12, 21), "1405 Q3"))
        self.assertEqual(t.persian_quarter(date(2026, 12, 22)), (date(2026, 12, 22), date(2027, 3, 20), "1405 Q4"))
        self.assertEqual(t.persian_quarter(date(2027, 3, 21))[2], "1406 Q1")
        self.assertEqual(t.to_jalali(date(2026, 12, 21)), (1405, 9, 30))
        self.assertEqual(t.to_jalali(date(2027, 3, 20)), (1405, 12, 29))

    # -- the contract in the engine --------------------------------------------------

    def test_04_whole_grams_and_the_residue_stays_cash(self):
        book = p.Book(p.START_CASH_IRR, 0)
        d = p.decide(book, 1.0, (BUY, SELL), traded_today=False)
        self.assertEqual(d.action, "BUY")
        self.assertEqual(d.grams, math.floor(p.START_CASH_IRR / BUY))
        self.assertIsInstance(d.grams, int)
        after = p.apply(book, d)
        self.assertAlmostEqual(after.cash, p.START_CASH_IRR - d.grams * BUY)
        self.assertGreater(after.cash, 0, "the residue stays in the account")
        self.assertLess(after.cash, BUY, "no whole gram was left unbought")

    def test_05_no_borrowing_and_no_short_selling(self):
        poor = p.Book(BUY * 0.9, 0)
        self.assertEqual(p.decide(poor, 1.0, (BUY, SELL), False).action, "HOLD", "cash below one gram")
        empty = p.Book(p.START_CASH_IRR, 0)
        self.assertEqual(p.decide(empty, 0.0, (BUY, SELL), False).action, "HOLD", "nothing to sell")
        held = p.Book(0.0, 3)
        sold = p.decide(held, 0.0, (BUY, SELL), False)
        self.assertEqual((sold.action, sold.grams), ("SELL", 3))
        self.assertGreaterEqual(p.apply(held, sold).grams, 0)

    def test_06_one_trade_a_day_and_a_fresh_price(self):
        book = p.Book(p.START_CASH_IRR, 0)
        self.assertEqual(p.decide(book, 1.0, (BUY, SELL), traded_today=True).action, "HOLD")
        self.assertEqual(p.decide(book, 1.0, None, traded_today=False).action, "HOLD")
        self.assertIsNone(p.venue_quote(_markets(status="ERROR: 403")))
        self.assertIsNone(p.venue_quote({"Goldika": {"price": BUY, "status": "OK"}}), "both sides or nothing")
        self.assertIsNone(p.venue_quote(_markets(buy=SELL, sell=BUY)), "a sell above the buy is not a quote")
        self.assertEqual(p.venue_quote(_markets()), (BUY, SELL))

    def test_07_buys_at_the_buy_price_and_sells_at_the_sell_price(self):
        self.assertEqual(p.decide(p.Book(p.START_CASH_IRR, 0), 1.0, (BUY, SELL), False).price, BUY)
        self.assertEqual(p.decide(p.Book(0.0, 3), 0.0, (BUY, SELL), False).price, SELL)
        self.assertEqual(p.Book(10.0, 3).value(SELL), 10.0 + 3 * SELL, "valued at what selling would pay")

    def test_08_analyst_v0_is_out_only_on_a_confirmed_break(self):
        ok = {"broke": False, "back": False, "rally_started": False}
        self.assertEqual(p.analyst_target(ok, was_out=False)[:2], (1.0, False))
        broke = dict(ok, broke=True)
        self.assertEqual(p.analyst_target(broke, was_out=False)[:2], (0.0, True))
        self.assertEqual(p.analyst_target(ok, was_out=True)[:2], (0.0, True), "no recovery yet: still out")
        self.assertEqual(p.analyst_target(dict(ok, back=True), was_out=True)[:2], (1.0, False))
        rising = p.signals(_uptrend())
        self.assertFalse(rising["broke"])
        crash = _uptrend(300) + [_uptrend(300)[-1] * 0.995 ** k for k in range(1, 40)]
        self.assertTrue(p.signals(crash)["broke"], "8% off the peak and below the 50-day")

    def test_09_conflicts_are_named(self):
        self.assertEqual(p.conflicts(1.0, 1, "WAIT"), [])
        self.assertIn("analyst stance bearish while v0 stays invested", p.conflicts(1.0, -2, "WAIT"))
        self.assertIn("system BUY while v0 is out", p.conflicts(0.0, 0, "BUY"))

    def test_10_the_account_reads_the_system_decision_and_never_makes_one(self):
        source = inspect.getsource(p)
        for name in ("build_signal_state", "save_market_state", "send_buy_signal", "resolve_signal_confirmation"):
            self.assertNotIn(name, source)
        self.assertEqual(p.system_target("BUY", 0.0)[0], 1.0)
        self.assertEqual(p.system_target("WAIT", 0.4)[0], 0.4)

    # -- the engine against a database -------------------------------------------------

    def _db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.connection import Base
        from database.models import MarketDailyCandle
        import main
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        s = Session()
        start = date(2025, 8, 1)
        for k, close in enumerate(_uptrend()):
            s.add(MarketDailyCandle(source="tgju", instrument="TGJU_GOLD_18K", trade_date=start + timedelta(days=k),
                                    open=close, high=close * 1.005, low=close * 0.995, close=close, unit="IRR",
                                    source_quality="COMPLETE", collected_at=datetime(2026, 1, 1)))
        s.commit()
        s.close()
        self._orig = main.get_session
        main.get_session = Session
        import alerts.telegram_paper as tp
        self._orig_send = tp.send_paper
        self.sent = []
        tp.send_paper = self.sent.append
        return main, Session

    def tearDown(self):
        if hasattr(self, "_orig"):
            import main
            import alerts.telegram_paper as tp
            main.get_session = self._orig
            tp.send_paper = self._orig_send

    def test_11_a_day_of_runs(self):
        from database.models import PaperAccount, PaperActivity
        main, Session = self._db()
        utc = lambda hh, mm=30: datetime(2026, 10, 4, hh, mm)          # Tehran = UTC + 3:30
        main._paper_run({}, _State(), utc(2, 31))                       # 06:01, Goldika missing
        main._paper_run(_markets(), _State(), utc(3, 31))               # 07:01
        main._paper_run(_markets(), _State(), utc(4, 31))               # 08:01
        s = Session()
        accounts = {a.name: a for a in s.query(PaperAccount)}
        self.assertEqual(set(accounts), {p.ANALYST, p.HOLD, p.SYSTEM})
        trades = s.query(PaperActivity).filter(PaperActivity.kind == "TRADE").all()
        by = {accounts[name].id: name for name in accounts}
        self.assertEqual(sorted(by[x.account_id] for x in trades), sorted([p.HOLD, p.ANALYST]),
                         "analyst and hold buy at the first fresh price; the system account waits for a BUY")
        for x in trades:
            self.assertEqual((x.action, x.grams), ("BUY", 3))
            self.assertAlmostEqual(float(x.cash), p.START_CASH_IRR - 3 * BUY, places=0)
            self.assertEqual(x.at, utc(3, 31), "not at 06:01, which had no fresh price")
        evals = s.query(PaperActivity).filter(PaperActivity.kind == "EVAL").order_by(PaperActivity.id).all()
        self.assertEqual(len(evals), 2, "the analyst logs every run it does not trade")
        self.assertIn("no fresh Goldika", evals[0].reason)
        self.assertIn("already traded today", evals[1].reason)
        self.assertEqual(len([m for m in self.sent if "PAPER BUY" in m]), 1, "only the analyst pushes")

        main._paper_run(_markets(), _State(), utc(17, 31))              # 21:01
        main._paper_run(_markets(), _State(), utc(17, 45))              # a second run after 21:00
        reports = s.query(PaperActivity).filter(PaperActivity.kind == "REPORT").all()
        self.assertEqual(len(reports), 3, "one report per account per day")
        report = [m for m in self.sent if "GOLDPremium: PAPER</b> ·" in m]
        self.assertEqual(len(report), 1)
        text = re.sub(r"</?[bi]>", "", report[0])
        self.assertIn("12 Mehr 1405, 21:00", text)
        self.assertIn("Gold: 3 g", text)
        self.assertIn("Total:", text)
        self.assertIn("This quarter (since 12 Mehr):", text)
        self.assertIn("Holding from the start instead:", text)
        s.close()

    def test_12_the_database_refuses_a_second_trade_a_day(self):
        from sqlalchemy.exc import IntegrityError
        from database.repository import ensure_paper_accounts, save_paper_activity
        main, Session = self._db()
        s = Session()
        acct = ensure_paper_accounts(s, p.ACCOUNTS, p.START_CASH_IRR, p.VENUE, datetime(2026, 10, 4, 3))[p.ANALYST]
        row = dict(account_id=acct.id, at=datetime(2026, 10, 4, 3), local_date=date(2026, 10, 4), kind="TRADE",
                   action="BUY", grams=1, price=BUY, cash=0, holding=1)
        save_paper_activity(s, **row)
        with self.assertRaises(IntegrityError):
            save_paper_activity(s, **row)
        s.rollback()
        s.close()

    def test_13_the_quarter_base_is_its_first_day(self):
        from database.repository import ensure_paper_accounts, paper_value_before, save_paper_activity
        main, Session = self._db()
        s = Session()
        acct = ensure_paper_accounts(s, p.ACCOUNTS, p.START_CASH_IRR, p.VENUE, datetime(2026, 10, 4, 3))[p.ANALYST]
        for day, value in ((date(2026, 12, 20), 1.05e9), (date(2026, 12, 21), 1.10e9), (date(2026, 12, 22), 1.20e9)):
            save_paper_activity(s, account_id=acct.id, at=datetime.combine(day, datetime.min.time()), local_date=day,
                                kind="REPORT", cash=value, holding=0, value=value)
        first = t.persian_quarter(date(2026, 12, 25))[0]
        self.assertEqual(first, date(2026, 12, 22))
        self.assertEqual(paper_value_before(s, acct.id, first), 1.10e9, "Q4 is measured from 30 Azar's close")
        self.assertIsNone(paper_value_before(s, acct.id, date(2026, 10, 4)), "the first quarter from the start cash")
        s.close()

    def test_14_the_run_never_raises(self):
        import main
        orig = main.get_session

        class _Broken:
            def query(self, *a, **k):
                raise RuntimeError("no database")

            def rollback(self):
                pass

            def close(self):
                pass
        main.get_session = _Broken
        try:
            main._paper_run(_markets(), _State(), datetime(2026, 10, 4, 3))
        finally:
            main.get_session = orig

    # -- messages ---------------------------------------------------------------------

    def test_15_messages_are_paper_plain_and_telegram_safe(self):
        from alerts.telegram_paper import build_report_message, build_trade_message
        trade = build_trade_message("BUY", 3, BUY, "Goldika", datetime(2026, 10, 4, 2, 31),
                                    "uptrend intact: no confirmed break", 3, 1e9 - 3 * BUY, SELL)
        sig = p.signals(_uptrend())
        report = build_report_message(date(2026, 10, 4), "Goldika", SELL, "", (3, 1e9 - 3 * BUY, 1e9),
                                      (3, 1e9 - 3 * BUY, 1e9), date(2026, 10, 4), [("BUY", 3, BUY, "06:01")],
                                      sig, False)
        for html in (trade, report):
            self.assertIn("PAPER", html)
            bare = re.sub(r"</?[bi]>", "", html)
            for char in "<>&":
                self.assertNotIn(char, bare)
            for word in BANNED:
                self.assertNotIn(word, bare.lower())
        self.assertIn("Bought 3 g at 26.60M (Goldika) · 12 Mehr 06:01", re.sub(r"</?[bi]>", "", trade))
        self.assertLess(len(re.sub(r"</?[bi]>", "", report)), 900, "read on a phone")

    # -- data and storage -------------------------------------------------------------

    def test_16_both_sides_survive_collection(self):
        from collector import iran
        name, info = iran._run_collector(lambda: {"platform": "Goldika", "price": BUY, "buy": BUY, "sell": SELL})
        self.assertEqual((info["buy"], info["sell"]), (BUY, SELL))
        import collector.daric as daric

        class _R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"Data": {"BestBuyPrice": "26393735", "BestSellPrice": "26461596"}}
        orig = daric.requests.get
        daric.requests.get = lambda *a, **k: _R()
        try:
            q = daric.get_daric_price()
        finally:
            daric.requests.get = orig
        self.assertEqual((q["buy"], q["sell"]), (264615960.0, 263937350.0),
                         "a buyer pays the lowest offer, a seller gets the highest bid")

    def test_17_the_migration_matches_the_models_and_is_additive(self):
        from database.models import PaperAccount, PaperActivity
        root = os.path.join(os.path.dirname(__file__), "..", "sql")
        sql = open(os.path.join(root, "neon_migration_paper.sql"), encoding="utf-8").read()
        schema = open(os.path.join(root, "neon_schema.sql"), encoding="utf-8").read()
        for model in (PaperAccount, PaperActivity):
            for column in model.__table__.columns:
                self.assertRegex(sql, rf"(?m)^\s+{column.name} ", f"{model.__tablename__}.{column.name}")
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {model.__tablename__}", schema)
        self.assertIn("WHERE kind = 'TRADE'", sql)
        self.assertIn("WHERE kind = 'REPORT'", sql)
        executable = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        self.assertNotRegex(executable, r"(?i)\b(ALTER|DROP|DELETE|UPDATE|INSERT)\b")

    def test_18_wired_into_the_scheduled_run_only(self):
        import main
        source = inspect.getsource(main.main)
        self.assertIn("_paper_run(markets, signal_state, now)", source)
        scheduled = source.index("if is_scheduled:")
        self.assertGreater(source.index("_paper_run(markets, signal_state, now)"), scheduled)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(KPIPaper)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print()
    print("=" * 55)
    print(f"PAPER KPI RESULT: {passed}/{total} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
