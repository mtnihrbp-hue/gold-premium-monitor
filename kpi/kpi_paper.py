"""KPI -- SP-D PAPER portfolio: the owner's contract, held in code and in the database.

The owner's scenario (2026-10-04): the analyst trades a hypothetical 135,000,000 toman in
whole grams of 18K, at most once a day at any run, on Daric then Goldika then Ayyareh,
reports at 21:00 and is reviewed per Persian quarter. It is a brave trader: a held core
and a swing part sold at +5% and bought back 2% lower or within 5 trading days. The
load-bearing properties are the contract's clauses:

- whole grams only, the residue stays as cash; no borrowing, no short selling;
- at most one trade per account per Tehran day, held by the engine AND by the database;
- no trade without a fresh two-sided quote on some venue of the chain;
- one report per day from 21:00, valued at a sell price, against the quarter's first
  day; quarters are Persian seasons;
- every analyst run is logged with its inputs, UNDECIDED where the signals conflict;
- messages are labelled PAPER, keep the vocabulary and are Telegram-safe;
- the account never decides for the system: it reads final_decision, never makes one;
- collection keeps both sides of a quote, and a refused source can go through the relay.
"""

import inspect
import io
import math
import os
import re
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

from analysis import paper as p
import timeutil as t

BANNED = ("widening", "widened", "narrowing", "grew", "smaller", "falling", "dearer", "dearest",
          "deepening", "cheap")
BUY, SELL = 266_035_936.0, 259_726_784.0          # Goldika, 2026-10-04 10:35 (rial)
Q = p.Quote("Goldika", BUY, SELL)
DAY = date(2026, 10, 4)


def _markets(buy=BUY, sell=SELL, status="OK", venue="Goldika"):
    return {venue: {"price": buy, "buy": buy, "sell": sell, "status": status},
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
        self.assertEqual(t.persian_day(DAY, year=True), "12 Mehr 1405")

    def test_02_every_day_round_trips(self):
        day = t.from_jalali(1390, 1, 1)
        while day < t.from_jalali(1420, 1, 1):
            self.assertEqual(t.from_jalali(*t.to_jalali(day)), day)
            day += timedelta(days=1)

    def test_03_quarters_are_persian_seasons(self):
        # owner, 2026-10-04: "ends in 30 of Azar, next starts at 1st of Dey, ends 29 Esfand"
        self.assertEqual(t.persian_quarter(DAY), (date(2026, 9, 23), date(2026, 12, 21), "1405 Q3"))
        self.assertEqual(t.persian_quarter(date(2026, 12, 22)), (date(2026, 12, 22), date(2027, 3, 20), "1405 Q4"))
        self.assertEqual(t.persian_quarter(date(2027, 3, 21))[2], "1406 Q1")
        self.assertEqual(t.to_jalali(date(2026, 12, 21)), (1405, 9, 30))
        self.assertEqual(t.to_jalali(date(2027, 3, 20)), (1405, 12, 29))

    # -- the contract ------------------------------------------------------------------

    def test_04_capital_leaves_a_small_residue(self):
        # owner: "a number that the residue is around 1 to 2%"
        self.assertEqual(p.START_CASH_IRR, 1_350_000_000)
        for buy in (264_615_960.0, BUY, 267_682_964.0):   # Daric's offer, Goldika's buy (10-04)
            grams = int(p.START_CASH_IRR // buy)
            self.assertEqual(grams, 5)
            self.assertLess((p.START_CASH_IRR - grams * buy) / p.START_CASH_IRR, 0.021)

    def test_05_the_venue_chain(self):
        both = {**_markets(venue="Goldika"), **_markets(buy=BUY * 0.99, sell=BUY * 0.987, venue="Daric")}
        self.assertEqual(p.venue_quote(both).venue, "Daric", "Daric first")
        self.assertEqual(p.venue_quote(_markets(venue="Goldika")).venue, "Goldika")
        self.assertEqual(p.venue_quote(_markets(venue="Ayyareh")).venue, "Ayyareh")
        self.assertIsNone(p.venue_quote({"Milli": {"price": BUY, "status": "OK"}}), "both sides or nothing")
        self.assertIsNone(p.venue_quote(_markets(status="ERROR: 403")))
        self.assertIsNone(p.venue_quote(_markets(buy=SELL, sell=BUY)), "a sell above the buy is not a quote")

    def test_06_whole_grams_no_borrowing_no_short(self):
        d = p.brave(p.Book(p.START_CASH_IRR, 0), Q, {}, DAY, False)
        self.assertEqual((d.action, d.grams, d.price), ("BUY", 5, BUY))
        after = p.apply(p.Book(p.START_CASH_IRR, 0), d)
        self.assertAlmostEqual(after.cash, p.START_CASH_IRR - 5 * BUY)
        self.assertGreater(after.cash, 0, "the residue stays in the account")
        self.assertEqual(d.swing["grams"], 1, "a fifth of 5 g is traded")
        self.assertEqual(p.brave(p.Book(BUY * 0.5, 0), Q, {}, DAY, False).action, "HOLD", "no borrowing")
        self.assertEqual(p.decide(p.Book(p.START_CASH_IRR, 0), 0.0, Q, False).action, "HOLD", "nothing to sell")
        self.assertEqual(p.decide(p.Book(0.0, 3), 0.0, Q, False).grams, 3)

    def test_07_two_trades_a_day_and_a_fresh_price(self):
        # owner, 2026-10-04: "expand the buy sell window from one daily to max 2 daily"
        self.assertEqual(p.MAX_TRADES_PER_DAY, 2)
        self.assertEqual(p.brave(p.Book(p.START_CASH_IRR, 0), Q, {}, DAY, traded_today=1).action, "BUY",
                         "a second trade the same day is allowed")
        self.assertEqual(p.brave(p.Book(p.START_CASH_IRR, 0), Q, {}, DAY, traded_today=2).action, "HOLD")
        self.assertEqual(p.brave(p.Book(p.START_CASH_IRR, 0), None, {}, DAY, 0).action, "HOLD")
        self.assertEqual(p.decide(p.Book(p.START_CASH_IRR, 0), 1.0, Q, traded_today=2).action, "HOLD")

    # -- the brave analyst -----------------------------------------------------------

    def test_08_takes_its_profit_at_plus_three(self):
        # owner, 2026-10-04: "faster is better"
        self.assertEqual((p.TAKE_PCT, p.RE_BUY_PCT), (3.0, 1.5))
        swing = {"grams": 1, "entry": BUY, "sold_at": None, "sold_day": None}
        book = p.Book(10_000_000.0, 5)
        below = p.Quote("Daric", BUY * 1.03, BUY * 1.029)
        self.assertEqual(p.brave(book, below, swing, DAY, 0).action, "HOLD", "+2.9% is not +3%")
        hit = p.Quote("Daric", BUY * 1.033, BUY * 1.031)
        d = p.brave(book, hit, swing, DAY, 0)
        self.assertEqual((d.action, d.grams, d.price), ("SELL", 1, BUY * 1.031), "sold at the sell price")
        self.assertEqual(d.swing["sold_at"], BUY * 1.031)
        self.assertIn("buy 1 g back", d.plan)

    def test_09_buys_back_lower_or_within_five_days(self):
        sold = {"grams": 1, "entry": BUY, "sold_at": BUY, "sold_day": "2026-10-04"}
        book = p.Book(BUY * 1.2, 4)
        flat = p.Quote("Daric", BUY * 0.99, BUY * 0.988)
        self.assertEqual(p.brave(book, flat, sold, date(2026, 10, 5), False).action, "HOLD", "-1% is not -1.5%")
        lower = p.Quote("Daric", BUY * 0.979, BUY * 0.976)
        d = p.brave(book, lower, sold, date(2026, 10, 5), False)
        self.assertEqual((d.action, d.grams), ("BUY", 1))
        self.assertIsNone(d.swing["sold_at"])
        # five trading days later (Friday skipped): back in whatever the price
        late = p.brave(book, p.Quote("Daric", BUY * 1.03, BUY * 1.028), sold, date(2026, 10, 10), False)
        self.assertEqual(late.action, "BUY", "a rising market is not missed for long")
        early = p.brave(book, p.Quote("Daric", BUY * 1.03, BUY * 1.028), sold, date(2026, 10, 8), False)
        self.assertEqual(early.action, "HOLD", "four trading days: still waiting")

    def test_10_stays_fully_invested_when_cash_covers_a_gram(self):
        swing = {"grams": 1, "entry": BUY, "sold_at": None, "sold_day": None}
        d = p.brave(p.Book(BUY * 1.5, 5), Q, swing, DAY, False)
        self.assertEqual((d.action, d.grams), ("BUY", 1))

    def test_11_conflicts_are_named_and_v0_still_runs(self):
        held = {"grams": 1, "entry": BUY, "sold_at": None, "sold_day": None}
        self.assertEqual(p.conflicts(1, "WAIT", held), [])
        self.assertIn("analyst stance bearish while the swing is held", p.conflicts(-2, "WAIT", held))
        ok = {"broke": False, "back": False, "rally_started": False}
        self.assertEqual(p.analyst_target(dict(ok, broke=True), was_out=False)[:2], (0.0, True))
        self.assertFalse(p.signals(_uptrend())["broke"])

    def test_12_the_account_reads_the_system_decision_and_never_makes_one(self):
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
        self._orig_send, self._orig_report = tp.send_paper, tp.send_paper_report
        self.sent, self.charts = [], []
        tp.send_paper = self.sent.append
        tp.send_paper_report = lambda text, png=None: (self.sent.append(text), self.charts.append(png))
        return main, Session

    def tearDown(self):
        if hasattr(self, "_orig"):
            import main
            import alerts.telegram_paper as tp
            main.get_session = self._orig
            tp.send_paper, tp.send_paper_report = self._orig_send, self._orig_report

    def test_13_a_day_of_runs(self):
        from database.models import PaperAccount, PaperActivity
        main, Session = self._db()
        utc = lambda hh, mm=30: datetime(2026, 10, 4, hh, mm)          # Tehran = UTC + 3:30
        main._paper_run({}, _State(), utc(2, 31))                       # 06:01, no venue price
        main._paper_run(_markets(), _State(), utc(3, 31))               # 07:01
        main._paper_run(_markets(), _State(), utc(4, 31))               # 08:01
        s = Session()
        accounts = {a.name: a for a in s.query(PaperAccount)}
        self.assertEqual(set(accounts), {p.ROOM, p.ANALYST, p.QUANT, p.CAUTIOUS, p.HOLD, p.SYSTEM})
        self.assertEqual({a.name for a in accounts.values() if a.pushes}, {p.ROOM}, "one front office")
        by = {accounts[name].id: name for name in accounts}
        trades = s.query(PaperActivity).filter(PaperActivity.kind == "TRADE").all()
        self.assertEqual(sorted(by[x.account_id] for x in trades), sorted([p.ROOM, p.ANALYST, p.CAUTIOUS, p.HOLD]),
                         "four buy at the first fresh price; the system account waits for a BUY")
        for x in trades:
            self.assertEqual((x.action, x.grams), ("BUY", 5))
            self.assertEqual(x.at, utc(3, 31), "not at 06:01, which had no fresh price")
            self.assertEqual(x.inputs["quote"]["venue"], "Goldika")
        analyst_evals = (s.query(PaperActivity).filter(PaperActivity.kind == "EVAL",
                                                         PaperActivity.account_id == accounts[p.ANALYST].id)
                         .order_by(PaperActivity.id).all())
        self.assertEqual(len(analyst_evals), 2, "the analyst logs every run it does not trade")
        self.assertIn("no fresh buy and sell price", analyst_evals[0].reason)
        self.assertIn("waiting for +3%", analyst_evals[1].reason, "a second trade is allowed; it simply has no reason yet")
        self.assertEqual(analyst_evals[1].inputs["swing"]["grams"], 1, "the swing state carries over")
        pushes = [m for m in self.sent if "PAPER" in m and "21:00" not in m]
        self.assertEqual(len(pushes), 1, "only the room pushes")
        self.assertIn("PAPER · the room", pushes[0])
        self.assertIn("Bought 5 g at", pushes[0])
        room_evals = (s.query(PaperActivity).filter(PaperActivity.kind == "EVAL",
                                                      PaperActivity.account_id == accounts[p.ROOM].id).all())
        self.assertEqual(len(room_evals), 2, "the room logs every run it does not trade")
        self.assertIn("no room view: the default, all in gold", room_evals[-1].reason,
                      "without enough history the room holds its default: gold")

        main._paper_run(_markets(), _State(), utc(17, 31))              # 21:01
        main._paper_run(_markets(), _State(), utc(17, 45))              # a second run after 21:00
        reports = s.query(PaperActivity).filter(PaperActivity.kind == "REPORT").all()
        self.assertEqual(len(reports), 6, "one report per account per day")
        report = [m for m in self.sent if "GOLDPremium: PAPER</b> ·" in m]
        self.assertEqual(len(report), 1)
        text = re.sub(r"</?[bi]>", "", report[0])
        for part in ("12 Mehr 1405, 21:00", "Posture: all in gold · 5 g", "Total:", "this quarter",
                     "Holding instead:", "Today: bought 5 g", "on Goldika", "The room: no view yet"):
            self.assertIn(part, text)
        self.assertTrue(self.charts and self.charts[0][1:4] == b"PNG", "the report carries its chart")
        s.close()

    def test_13b_the_quant_engine(self):
        from analysis import quant
        self.assertEqual(quant.growth_share(0.002, 0.0004), 1.0, "mu/sigma^2 = 5, capped at 1")
        self.assertAlmostEqual(quant.growth_share(0.0002, 0.0004), 0.5)
        self.assertEqual(quant.growth_share(-0.001, 0.0004), 0.0, "no short selling")
        self.assertEqual(quant.cost_band(1.0, 0.30), 0.0, "no band at the edge")
        self.assertAlmostEqual(quant.cost_band(0.5, 0.30), (1.5 * 0.003 * 0.25 * 0.25) ** (1 / 3))
        rng = __import__("numpy").random.default_rng(3)
        calm = rng.normal(0.0015, 0.008, 700)
        storm = rng.normal(0.001, 0.06, 60)
        close = list(150_000_000 * __import__("numpy").exp(__import__("numpy").cumsum(__import__("numpy").concatenate([calm, storm]))))
        view = quant.assess(close)
        self.assertIsNotNone(view)
        self.assertLess(view["f_star"], 0.6, "in a storm the growth-optimal share falls: the brake")
        self.assertIsNone(quant.assess(close[:300]), "too little history is no answer")

    def test_13c_the_brake_sells_down_in_a_storm(self):
        swing = {"grams": 1, "entry": BUY, "sold_at": None, "sold_day": None}
        d = p.brave(p.Book(10_000_000.0, 5), Q, swing, DAY, False, cap=0.5)
        self.assertEqual(d.action, "SELL")
        self.assertEqual(d.grams, 5 - int((10_000_000.0 + 5 * SELL) * 0.5 // SELL))
        self.assertIn("volatility brake", d.reason)
        opening = p.brave(p.Book(p.START_CASH_IRR, 0), Q, {}, DAY, False, cap=0.6)
        self.assertEqual(opening.grams, int(p.START_CASH_IRR * 0.6 // BUY), "it buys only up to the brake")
        self.assertEqual(p.brave(p.Book(p.START_CASH_IRR, 0), Q, {}, DAY, False, cap=None).grams, 5)

    def test_13d_the_report_goes_out_with_its_chart(self):
        import alerts.telegram as tg
        import alerts.telegram_paper as tp
        from alerts.chart import render
        days = [date(2026, 5, 1) + timedelta(days=k) for k in range(150)]
        close = _uptrend(150)
        png = render(days, close, [x * 1.005 for x in close], [x * 0.995 for x in close], close,
                     supports=[close[-30]], trades=[(days[-1], "BUY", close[-1])], live=close[-1] * 1.01)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        sent = {}
        orig_photo, orig_send = tg._send_photo, tp._send
        try:
            tg._send_photo = lambda png_, caption: sent.update(photo=len(png_), caption=caption) or True
            tp._send = lambda text: sent.update(text=text)
            tp.send_paper_report("<b>GOLDPremium: PAPER</b> report", png)
            self.assertIn("photo", sent)
            self.assertNotIn("text", sent, "the report is the photo's caption")
            sent.clear()
            tp.send_paper_report("<b>GOLDPremium: PAPER</b> report", None)
            self.assertIn("text", sent, "no chart: the text alone")
        finally:
            tg._send_photo, tp._send = orig_photo, orig_send

    def test_13e_trend_lines_and_fibonacci(self):
        import numpy as np
        from caluclator.technical import fibonacci, trendlines
        # a rising zigzag: lows rise, highs rise
        k = np.arange(160)
        close = 100 + 0.2 * k + 3 * np.sin(k / 6)
        high, low = close * 1.004, close * 0.996
        t = trendlines(high, low, close, upto=159)
        sup, res = t["support"], t["resistance"]
        self.assertIsNotNone(sup)
        self.assertIsNotNone(res)
        self.assertGreater(sup["slope_pct_per_day"], 0, "rising lows give a rising support line")
        self.assertLessEqual(sup["at"], close[159])
        self.assertGreaterEqual(res["at"], close[159])
        line = sup["y1"] + (sup["y2"] - sup["y1"]) / (sup["i2"] - sup["i1"]) * (np.arange(sup["i1"], 160) - sup["i1"])
        self.assertTrue(np.all(close[sup["i1"]:] >= line * 0.995), "no close crosses its support line")
        self.assertTrue(sup["i2"] <= 159 - 5, "a swing counts only once confirmed")
        levels = dict(fibonacci(100.0, 200.0))
        self.assertAlmostEqual(levels[0.382], 161.8)
        self.assertAlmostEqual(levels[0.618], 138.2)

    def test_14_the_database_refuses_a_third_trade_a_day(self):
        from sqlalchemy.exc import IntegrityError
        from database.repository import ensure_paper_accounts, save_paper_activity
        main, Session = self._db()
        s = Session()
        acct = ensure_paper_accounts(s, p.ACCOUNTS, p.START_CASH_IRR, "chain", datetime(2026, 10, 4, 3))[p.ANALYST]
        row = dict(account_id=acct.id, at=datetime(2026, 10, 4, 3), local_date=DAY, kind="TRADE",
                   action="BUY", grams=1, price=BUY, cash=0, holding=1)
        save_paper_activity(s, **row, trade_no=1)
        save_paper_activity(s, **row, trade_no=2)
        for bad in (2, 3):                                  # a duplicate number, and a third trade
            with self.assertRaises(IntegrityError):
                save_paper_activity(s, **row, trade_no=bad)
            s.rollback()
        s.close()

    def test_14b_the_two_trade_migration_matches_the_model(self):
        from database.models import PaperActivity
        root = os.path.join(os.path.dirname(__file__), "..", "sql")
        sql = open(os.path.join(root, "neon_migration_paper_two_trades.sql"), encoding="utf-8").read()
        schema = open(os.path.join(root, "neon_schema.sql"), encoding="utf-8").read()
        self.assertIn("trade_no", PaperActivity.__table__.columns)
        for part in ("ADD COLUMN IF NOT EXISTS trade_no SMALLINT", "DROP INDEX IF EXISTS uq_paper_one_trade_a_day",
                     "uq_paper_trade_slot", "ON paper_activity (account_id, local_date, trade_no) WHERE kind = 'TRADE'",
                     "CHECK (kind <> 'TRADE' OR trade_no IN (1, 2))"):
            self.assertIn(part, sql)
        self.assertIn("uq_paper_trade_slot", schema)
        self.assertNotIn("uq_paper_one_trade_a_day\n    ON", schema, "the target schema holds the new index only")

    def test_15_the_quarter_base_is_its_first_day(self):
        from database.repository import ensure_paper_accounts, paper_value_before, save_paper_activity
        main, Session = self._db()
        s = Session()
        acct = ensure_paper_accounts(s, p.ACCOUNTS, p.START_CASH_IRR, "chain", datetime(2026, 10, 4, 3))[p.ANALYST]
        for day, value in ((date(2026, 12, 20), 1.40e9), (date(2026, 12, 21), 1.45e9), (date(2026, 12, 22), 1.50e9)):
            save_paper_activity(s, account_id=acct.id, at=datetime.combine(day, datetime.min.time()), local_date=day,
                                kind="REPORT", cash=value, holding=0, value=value)
        first = t.persian_quarter(date(2026, 12, 25))[0]
        self.assertEqual(paper_value_before(s, acct.id, first), 1.45e9, "Q4 is measured from 30 Azar's close")
        self.assertIsNone(paper_value_before(s, acct.id, DAY), "the first quarter from the start cash")
        s.close()

    def test_16_the_run_never_raises(self):
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

    def test_17_messages_are_paper_plain_and_telegram_safe(self):
        from alerts.telegram_paper import build_report_message, build_trade_message
        trade = build_trade_message("SELL", 1, 278_000_000.0, "Daric", datetime(2026, 10, 7, 10, 31),
                                    "+5.1% over its 26.46M cost: profit taken", 4, 300_000_000.0, 277_000_000.0,
                                    "buy 1 g back at 27.24M or less, or on 22 Mehr at the latest")
        report = build_report_message(DAY, "Daric", 263_937_350.0, "", (5, 27_000_000.0, 1.35e9),
                                      (5, 27_000_000.0, 1.35e9), DAY, [("BUY", 5, 264_615_960.0, "Daric", "11:01")],
                                      "sell 1 g if a venue pays 27.78M or more (+5% over its cost)")
        for html in (trade, report):
            self.assertIn("PAPER", html)
            bare = re.sub(r"</?[bi]>", "", html)
            for char in "<>&":
                self.assertNotIn(char, bare)
            for word in BANNED:
                self.assertNotIn(word, bare.lower())
        plain = re.sub(r"</?[bi]>", "", trade)
        self.assertIn("Sold 1 g at 27.80M on Daric · 15 Mehr 14:01", plain)
        self.assertIn("Next: buy 1 g back", plain)
        self.assertLess(len(re.sub(r"</?[bi]>", "", report)), 900, "read on a phone")

    # -- data, the relay and storage ----------------------------------------------------

    def test_18_both_sides_survive_collection(self):
        from collector import iran
        name, info = iran._run_collector(lambda: {"platform": "Goldika", "price": BUY, "buy": BUY, "sell": SELL})
        self.assertEqual((info["buy"], info["sell"]), (BUY, SELL))
        import collector.relay as relay

        class _R:
            def __init__(self, data):
                self.data = data

            def raise_for_status(self):
                pass

            def json(self):
                return self.data
        orig = relay.requests.get
        try:
            relay.requests.get = lambda *a, **k: _R({"Data": {"BestBuyPrice": "26393735", "BestSellPrice": "26461596"}})
            from collector.daric import get_daric_price
            q = get_daric_price()
            self.assertEqual((q["buy"], q["sell"]), (264615960.0, 263937350.0),
                             "a buyer pays the lowest offer, a seller gets the highest bid")
        finally:
            relay.requests.get = orig
        import collector.ayyareh as ayyareh
        orig = ayyareh.requests.get
        try:
            ayyareh.requests.get = lambda *a, **k: _R({"goldPrice": 26677000, "sellWageValue": 0.01, "buyWageValue": 0.01})
            q = ayyareh.get_ayyareh_price()
        finally:
            ayyareh.requests.get = orig
        self.assertEqual(q["price"], 266770000.0, "the published price is unchanged for every other consumer")
        self.assertAlmostEqual(q["buy"], 266770000.0 * 1.01)
        self.assertAlmostEqual(q["sell"], 266770000.0 * 0.99)

    def test_19_a_refused_source_goes_through_the_relay(self):
        import requests
        import collector.relay as relay
        calls = []

        def fake_get(url, headers=None, timeout=None):
            calls.append((url, dict(headers or {})))
            if "relay.example" in url:
                class _OK:
                    def raise_for_status(self):
                        pass

                    def json(self):
                        return {"Data": {"BestBuyPrice": "1", "BestSellPrice": "2"}}
                return _OK()
            raise requests.exceptions.ConnectionError("refused")
        orig, env = relay.requests.get, dict(os.environ)
        try:
            relay.requests.get = fake_get
            os.environ.pop("RELAY_URL", None)
            os.environ.pop("RELAY_TOKEN", None)
            with self.assertRaises(requests.exceptions.ConnectionError):
                relay.get_json("https://apisc.daric.gold/x")
            os.environ.update(RELAY_URL="https://relay.example", RELAY_TOKEN="secret")
            self.assertEqual(relay.get_json("https://apisc.daric.gold/x")["Data"]["BestSellPrice"], "2")
            self.assertEqual(calls[-1][1]["X-Relay-Token"], "secret")
            self.assertIn("url=https%3A%2F%2Fapisc.daric.gold%2Fx", calls[-1][0])
        finally:
            relay.requests.get = orig
            os.environ.clear()
            os.environ.update(env)
        root = os.path.join(os.path.dirname(__file__), "..")
        wf = open(os.path.join(root, ".github", "workflows", "gold-monitor.yml"), encoding="utf-8").read()
        self.assertIn("RELAY_URL: ${{ secrets.RELAY_URL }}", wf)
        worker = open(os.path.join(root, "src", "worker", "data-relay.js"), encoding="utf-8").read()
        self.assertIn("X-Relay-Token", worker)
        self.assertIn("apisc\\.daric\\.gold", worker, "an allowlist, not an open proxy")

    def test_20_the_migration_matches_the_models_and_is_additive(self):
        from database.models import PaperAccount, PaperActivity
        root = os.path.join(os.path.dirname(__file__), "..", "sql")
        sql = open(os.path.join(root, "neon_migration_paper.sql"), encoding="utf-8").read()
        later = open(os.path.join(root, "neon_migration_paper_two_trades.sql"), encoding="utf-8").read()
        schema = open(os.path.join(root, "neon_schema.sql"), encoding="utf-8").read()
        for model in (PaperAccount, PaperActivity):
            for column in model.__table__.columns:
                self.assertRegex(sql + later, rf"(?m)(^\s+|ADD COLUMN IF NOT EXISTS ){column.name} ",
                                 f"{model.__tablename__}.{column.name}")
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {model.__tablename__}", schema)
        self.assertIn("WHERE kind = 'TRADE'", sql)
        self.assertIn("WHERE kind = 'REPORT'", sql)
        executable = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        self.assertNotRegex(executable, r"(?i)\b(ALTER|DROP|DELETE|UPDATE|INSERT)\b")

    def test_21_wired_into_the_scheduled_run_only(self):
        import main
        source = inspect.getsource(main.main)
        scheduled = source.index("if is_scheduled:")
        self.assertGreater(source.index("_paper_run(markets, signal_state, now)"), scheduled)

    # -- the room, the front office (SP_D_HANDOFF.md section 27) ------------------------------

    def test_22_the_room_replays_its_posture(self):
        import numpy as np
        from analysis import room
        n = 40
        out_members = ("brake", "market state", "fair gap", "real dollar")    # 6.5 of 9 weight: over 60%
        leans = {m: np.zeros(n, dtype=int) for m in room.WEIGHTS}
        for m in room.WEIGHTS:
            if m in out_members:
                leans[m][3:25] = -1
            else:
                leans[m][:] = 1
        stocks = np.zeros(n, dtype=int)
        path = room.replay(leans, stocks, 0, n - 1)
        self.assertTrue(path[3]["inner"], "the committee's view moves the day the weight crosses 60%")
        self.assertEqual(path[3]["posture"], room.ALL_GOLD, "the posture waits for a review day")
        self.assertEqual(path[10]["posture"], room.SWING_OUT, "the review on day 10 follows the view")
        self.assertFalse(path[25]["inner"], "back at 30% or less")
        self.assertEqual(path[25]["posture"], room.SWING_OUT, "and the posture waits for the next review")
        self.assertEqual(path[30]["posture"], room.ALL_GOLD, "the review on day 30 brings it back")
        stocks[12:] = 1                                                    # a new turn up after the sale
        path = room.replay(leans, stocks, 0, n - 1)
        self.assertEqual(path[12]["posture"], room.ALL_GOLD)
        self.assertTrue(path[12]["early"], "the sharp eye: back to gold early on a new turn up")
        stocks[:] = 1                                                      # a standing rise at the review
        path = room.replay(leans, stocks, 0, n - 1)
        self.assertEqual(path[10]["posture"], room.ALL_GOLD, "no sale while the stock index leans to gold")
        self.assertTrue(path[10]["vetoed"])
        self.assertEqual(room.share_for_fixed_income({m: np.array([1]) for m in room.WEIGHTS}, 0)[0], 0.0)

    def test_23_the_room_trades_whole_grams_and_parks_in_afran(self):
        from analysis.room import ALL_GOLD, SWING_OUT
        fund = 54_490.0
        d, b = p.room_trade(p.Book(p.START_CASH_IRR, 0), Q, ALL_GOLD, fund, 0)
        self.assertEqual((d.action, d.grams, b.units), ("BUY", 5, 0.0), "the default: all in gold")
        d, b2 = p.room_trade(b, Q, SWING_OUT, fund, 0)
        self.assertEqual((d.action, d.grams, b2.grams), ("SELL", 2, 3), "the owner's 2 of 5")
        self.assertEqual(b2.units, math.floor((b.cash + 2 * SELL) / fund), "the cash goes straight into Afran")
        self.assertLess(b2.cash, fund, "whole units, the residue as cash")
        self.assertAlmostEqual(b2.value(SELL, fund), b.value(SELL), delta=1, msg="moving money is not making it")
        self.assertEqual(p.room_trade(b2, Q, SWING_OUT, fund, 0)[0].action, "HOLD", "already out: nothing to do")
        d, b3 = p.room_trade(b2, Q, ALL_GOLD, fund * 1.01, 0)
        self.assertEqual((d.action, b3.units), ("BUY", 0.0), "back to gold: every unit comes out")
        self.assertEqual(b3.grams, 3 + int((b2.cash + b2.units * fund * 1.01) // BUY))
        self.assertEqual(p.room_trade(b, Q, SWING_OUT, None, 0)[0].action, "HOLD", "no Afran price: no sale")
        self.assertEqual(p.room_trade(b, Q, SWING_OUT, fund, p.MAX_TRADES_PER_DAY)[0].action, "HOLD")
        self.assertEqual(p.room_trade(b, None, SWING_OUT, fund, 0)[0].action, "HOLD", "no fresh quote: no trade")
        d, b4 = p.room_trade(p.Book(p.START_CASH_IRR, 0), Q, SWING_OUT, fund, 0)
        self.assertEqual((d.action, d.grams), ("BUY", 3), "opening while out: the core only, the rest in Afran")
        self.assertGreater(b4.units, 0)

    def test_24_the_room_is_eight_members_and_plain_words(self):
        from analysis import room
        self.assertEqual(set(room.WEIGHTS), {"brake", "market state", "fair gap", "real dollar", "dollar 20d",
                                             "world gold 60d", "chartist", "money flow"},
                         "money flow joined through the Iran-side node (SP_D_HANDOFF.md section 33)")
        self.assertEqual(room.WEIGHTS["money flow"], 0.5, "section 18's weight")
        self.assertEqual((room.LEAVE, room.BACK, room.REVIEW_EVERY, room.SWING), (0.60, 0.30, 10, 0.40))
        for text in room.WHY.values():
            for word in BANNED:
                self.assertNotIn(word, text.lower())

    def test_25_the_room_messages(self):
        from alerts.telegram_paper import build_room_report_message, build_room_trade_message
        from analysis.room import SWING_OUT
        view = {"posture": SWING_OUT, "reasons": ["the market is moving sideways", "the dollar decreased over 20 days"],
                "next_review": "2026-10-19", "members": {k: 0 for k in range(7)}, "for_fixed_income": [1, 2, 3, 4, 5],
                "for_gold": [6], "phase_line": "sideways after a rise (distribution), down from 26.10M on 5 Mehr",
                "band20": [240_000_000, 290_000_000, 230_000_000, 300_000_000, 265_000_000]}
        after = p.Book(7_150.0, 3, 9_965.0)
        sell = build_room_trade_message("SELL", 2, SELL, "Goldika", datetime(2026, 10, 5, 5, 31), view, after, 54_490.0,
                                        False, SELL, (p.START_CASH_IRR, DAY))
        back = build_room_trade_message("BUY", 2, BUY, "Daric", datetime(2026, 10, 19, 3, 31),
                                        dict(view, reasons=["the stock index turned up: back to gold early"]),
                                        p.Book(1_000_000.0, 5, 0.0), 55_000.0, True, SELL, (p.START_CASH_IRR, DAY), 9_965.0)
        report = build_room_report_message(DAY, "Goldika", SELL, "", 3, 9_965.0, 54_490.0, False,
                                           3 * SELL + 9_965 * 54_490.0, p.START_CASH_IRR, DAY, (1.40e9, 1.35e9), [], view)
        for html in (sell, back, report):
            self.assertIn("PAPER", html)
            bare = re.sub(r"</?[bi]>", "", html)
            for char in "<>&":
                self.assertNotIn(char, bare)
            for word in BANNED:
                self.assertNotIn(word, bare.lower())
            self.assertLessEqual(max(len(x) for x in bare.splitlines()), 110, "short lines, read on a phone")
        plain = re.sub(r"</?[bi]>", "", sell)
        for part in ("Sold 2 g at", "Moved to Afran (fixed income):", "Kept in gold: 3 g",
                     "Back to gold: when the stock index turns up, or at the review on 27 Mehr"):
            self.assertIn(part, plain)
        self.assertIn("an estimate", back, "an old Afran price says so")
        self.assertIn("Paid from Afran", back)
        plain = re.sub(r"</?[bi]>", "", report)
        for part in ("Phase: sideways after a rise", "Posture: 3 g in gold,", "in Afran (fixed income)",
                     "The room: 5 of 7 lean to fixed income, 1 to gold"):
            self.assertIn(part, plain)
        self.assertNotIn("Next 20 trading days", plain, "dropped for the buyers' line (owner, 2026-10-16)")

    def test_26_the_collectors_never_raise_and_read_their_pages(self):
        import requests
        import collector.etfbaz as eb
        import collector.tablokhani as tk

        class _R:
            def __init__(self, data):
                self.data = data

            def raise_for_status(self):
                pass

            def json(self):
                return self.data
        pages = {
            "market-indices": {"success": True, "data": {"bourse": {"state": "closed", "index": "7,790,017.18"}}},
            "smart-money-averages": {"success": True, "data": {tk.AFRAN: {"closing_1d_ago": 54490},
                                                               tk.GOLD_FUNDS[0]: {"avg_per_capita_buy_10d": 184.05}}},
        }
        landing = [{"items": [{"symbol": "USDT", "price": 2685890.0}, {"symbol": "USD", "price": 2692100.0}]}]
        orig = requests.get
        try:
            requests.get = lambda url, **k: _R(pages[url.rsplit("/", 1)[-1]]) if "tablokhani" in url else _R(landing)
            t = tk.collect()
            self.assertEqual((t["tedpix"], t["tse_state"], t["afran_close"]), (7790017.18, "closed", 54490.0))
            self.assertIn(tk.GOLD_FUNDS[0], t["funds"])
            e = eb.collect()
            self.assertEqual(e["ETFBAZ_USDT_IRR"], 2685890.0, "Tether, the dollar at night, from the runner")
            self.assertEqual(e["ETFBAZ_USD_IRR"], 2692100.0)

            def boom(*a, **k):
                raise requests.exceptions.ConnectionError("refused")
            requests.get = boom
            self.assertEqual(len(tk.collect()["errors"]), 2)
            self.assertEqual(eb.collect(), {"errors": ["landing: ConnectionError"]})
        finally:
            requests.get = orig

    def test_27_the_room_is_wired_with_its_seeds(self):
        import json as _json
        import main
        source = inspect.getsource(main.main)
        self.assertGreater(source.index("_collect_room_inputs(now)"), source.index("_collect_tgju_candles()"))
        self.assertLess(source.index("_collect_room_inputs(now)"), source.index("_paper_run(markets, signal_state, now)"))
        ted = _json.load(open(os.path.join(SRC_DIR, "seed", "tedpix.json")))
        fi = _json.load(open(os.path.join(SRC_DIR, "seed", "fixed_income.json")))
        self.assertGreater(len(ted), 4000)
        self.assertGreater(len(fi["level"]), 2500)
        self.assertGreater(fi["afran_scale"], 0)
        self.assertEqual(main.ROOM_INPUTS["AFRAN_LAST"], ("tablokhani", "IRR"))

    def test_29_every_text_fits_its_column(self):
        # SQLite, which these tests run on, does not enforce VARCHAR lengths; production's Postgres
        # does. The first live run on 2026-10-05 failed on paper_accounts.venue, VARCHAR(20), given
        # "Daric>Goldika>Ayyareh" (21). Every text the PAPER and room code writes, against its column.
        import main
        from collector.tgju import INSTRUMENTS, UNITS
        from database.models import MarketDailyCandle, PaperAccount, PaperActivity
        length = lambda model, col: model.__table__.c[col].type.length
        for name, policy, _ in p.ACCOUNTS:
            self.assertLessEqual(len(name), length(PaperAccount, "name"), name)
            self.assertLessEqual(len(policy), length(PaperAccount, "policy"), policy)
        self.assertLessEqual(len(p.VENUE_LABEL), length(PaperAccount, "venue"))
        self.assertLessEqual(len("ACTIVE"), length(PaperAccount, "status"))
        for kind in ("TRADE", "EVAL", "REPORT"):
            self.assertLessEqual(len(kind), length(PaperActivity, "kind"))
        for action in ("BUY", "SELL", "HOLD", "UNDECIDED"):
            self.assertLessEqual(len(action), length(PaperActivity, "action"))
        for instrument, (source, unit) in main.ROOM_INPUTS.items():
            self.assertLessEqual(len(instrument), length(MarketDailyCandle, "instrument"), instrument)
            self.assertLessEqual(len(source), length(MarketDailyCandle, "source"), source)
            self.assertLessEqual(len(unit), length(MarketDailyCandle, "unit"), unit)
        for instrument in INSTRUMENTS.values():
            self.assertLessEqual(len(instrument), length(MarketDailyCandle, "instrument"))
        for unit in UNITS.values():
            self.assertLessEqual(len(unit), length(MarketDailyCandle, "unit"))
        self.assertLessEqual(len("LAST_KNOWN"), length(MarketDailyCandle, "source_quality"))
        self.assertLessEqual(len("1405/07/13"), length(MarketDailyCandle, "trade_date_jalali"))

    def test_28_the_brake_path_matches_the_engine(self):
        import numpy as np
        from analysis import quant
        rng = np.random.default_rng(5)
        close = list(150_000_000 * np.exp(np.cumsum(rng.normal(0.0015, 0.01, 700))))
        view = quant.assess(close)
        f_path, mu = quant.growth_path(close, view["fitted"])
        self.assertEqual(len(f_path), len(close))
        self.assertAlmostEqual(f_path[-1], view["f_star"], places=9, msg="the last day is the engine's own f*")
        self.assertAlmostEqual(mu[-1], view["mu"], places=12)

    # -- the money-flow member (SP_D_HANDOFF.md section 33) -------------------------------

    def test_30_money_flow_is_the_research_member(self):
        """The buyer power's mean over its last 20 trading days, carried to 18K's days while the funds'
        last day is under a week old -- rd_committee_2y.py's construction, which the parity check
        (research/check_room_parity.py) matches on 100% of days since 2018."""
        import numpy as np
        from analysis import room
        fdays = [date(2026, 1, 1) + timedelta(days=k) for k in range(30)]
        power = [1.0 + 0.01 * k for k in range(30)]
        dates = [fdays[-1], fdays[-1] + timedelta(days=6), fdays[-1] + timedelta(days=7), fdays[10]]
        got = room.money_flow(dates, fdays, power)
        last20 = np.mean(power[-20:])
        self.assertAlmostEqual(got[0], last20, places=12)
        self.assertAlmostEqual(got[1], last20, places=12, msg="six days on, the last value stands")
        self.assertTrue(np.isnan(got[2]), "a week or more without the funds is no view")
        self.assertAlmostEqual(got[3], np.mean(power[:11]), places=12, msg="fewer than 20 days: their mean")

    def _flow_session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database.connection import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        return sessionmaker(bind=engine, expire_on_commit=False)()

    def test_31_production_appends_the_phones_days_after_the_seed(self):
        """A day after the seed counts when 15 of the 19 funds have it; a fund's latest copy of a day is
        the one used; days the seed holds are not replaced."""
        import json as _json
        import main
        from database.models import IranNodeReading
        seed = _json.load(open(os.path.join(SRC_DIR, "seed", "gold_fund_flows.json")))
        funds = seed["funds"]
        s = self._flow_session()

        def add(day, code, bv, bc, sv, sc, at):
            s.add(IranNodeReading(node="s10", source="tsetmc", instrument=f"CLIENTTYPE_{code}", observed_at=at,
                                  status="OK", detail=day, received_at=at,
                                  payload={"insCode": code, "recDate": int(day), "buy_I_Value": bv, "buy_I_Count": bc,
                                           "sell_I_Value": sv, "sell_I_Count": sc}))
        end = date.fromisoformat(max(seed["power"]))       # the seed's last day (refreshed, section 48)
        day1, day2 = end + timedelta(days=1), end + timedelta(days=2)
        t0 = datetime.combine(day2, datetime.min.time()) + timedelta(hours=9)
        for code in funds:                                  # day 1: every fund; one stale copy replaced
            add(day1.strftime("%Y%m%d"), code, 100.0, 10, 50.0, 10, t0)
        add(day1.strftime("%Y%m%d"), funds[0], 300.0, 10, 50.0, 10, t0 + timedelta(hours=1))
        for code in funds[:10]:                             # day 2: ten funds, too few
            add(day2.strftime("%Y%m%d"), code, 100.0, 10, 50.0, 10, t0)
        add(end.strftime("%Y%m%d"), funds[0], 999.0, 1, 1.0, 1, t0)     # the seed's own last day: not replaced
        s.commit()
        days, power = main._room_flow(s)
        got = dict(zip(days, power))
        n = len(funds)
        expect = ((100.0 * (n - 1) + 300.0) / (10 * n)) / ((50.0 * n) / (10 * n))
        self.assertAlmostEqual(got[day1], expect, places=12)
        self.assertNotIn(day2, got, "ten of the funds is not a day")
        self.assertAlmostEqual(got[end], seed["power"][end.isoformat()], places=12)
        s.close()

    def test_32_the_room_reads_the_flow_and_fails_safe(self):
        import json as _json
        import main
        seed = _json.load(open(os.path.join(SRC_DIR, "seed", "gold_fund_flows.json")))
        self.assertEqual(len(seed["funds"]), 19, "section 33's 18 gold funds and گنج (48); no saffron (49)")
        self.assertNotIn("51200575796028449", seed["funds"], "the saffron fund is gone (owner, 2026-10-18)")
        self.assertIn("58514988269776425", seed["funds"])
        self.assertGreater(len(seed["power"]), 1500)
        self.assertGreaterEqual(max(seed["power"]), "2026-10-17")
        source = inspect.getsource(main._room_state)
        self.assertIn("room.money_flow(dates, *_room_flow(session))", source)
        self.assertIn("flow=flow", source)
        self.assertIn("flow = None", source, "without the flow the member has no view; the room carries on")

    # -- the quant engine's fit (SP_D_HANDOFF.md section 35) --------------------------------

    def _returns(self):
        import numpy as np
        rng = np.random.default_rng(5)
        return np.diff(np.log(150_000_000 * np.exp(np.cumsum(rng.normal(0.0015, 0.01, 700)))))

    def test_33_the_fit_is_the_same_every_time_and_leaves_the_rest_random(self):
        import numpy as np
        from analysis import quant
        r = self._returns()
        np.random.seed(123)
        before = np.random.get_state()[1].copy()
        a, b = quant.fit_regimes(r), quant.fit_regimes(r)
        self.assertEqual(a["params"], b["params"], "an unseeded search fitted the same data two ways")
        self.assertEqual(a["seed"], quant.FIT_SEEDS[0])
        self.assertTrue((np.random.get_state()[1] == before).all(), "the program's random state is restored")

    def test_34_a_failed_search_is_retried_from_the_next_seed(self):
        """On 2026-10-07 one search did not converge and the engine reported itself unavailable."""
        import numpy as np
        import statsmodels.api as sm
        from analysis import quant
        real = sm.tsa.MarkovRegression.fit
        calls = []

        def flaky(self, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise np.linalg.LinAlgError("SVD did not converge")
            return real(self, *args, **kwargs)
        sm.tsa.MarkovRegression.fit = flaky
        try:
            with redirect_stdout(io.StringIO()):
                fit = quant.fit_regimes(self._returns())
        finally:
            sm.tsa.MarkovRegression.fit = real
        self.assertIsNotNone(fit)
        self.assertEqual(fit["seed"], quant.FIT_SEEDS[1])
        self.assertEqual(len(calls), 2)


    # -- the 21:00 chart without the database (SP_D_HANDOFF.md section 35.2) -------------

    def _wave(self, n=400, start=date(2025, 6, 1)):
        from persistence.candle_cache import Candle
        rows = []
        for k in range(n):
            c = 150_000_000 * 1.002 ** k * (1 + 0.08 * math.sin(k / 12))
            rows.append(Candle(start + timedelta(days=k), c * 0.998, c * 1.006, c * 0.994, c, "COMPLETE"))
        return rows

    def _evening(self, reachable, now, state):
        import main
        import alerts.telegram_paper as tp
        import persistence.candle_cache as cc
        from collector import tablokhani as tk
        sent, calls = [], []
        saved = (main._database_reachable, tp.send_paper_report, cc.direct, tk.collect)
        main._database_reachable = lambda: calls.append("checked") or reachable
        tp.send_paper_report = lambda text, png=None: sent.append((text, png))
        cc.direct = lambda instrument, today: calls.append((instrument, today)) or self._wave()
        tk.collect = lambda: {"flows": {s: (1e12, 4_000.0, 0.9e12, 2_000.0) for s in tk.GOLD_FUNDS}}   # no network
        try:
            with redirect_stdout(io.StringIO()):
                main._evening_fallback(_markets(), now, state)
        finally:
            main._database_reachable, tp.send_paper_report, cc.direct, tk.collect = saved
        return sent, calls

    def test_35_the_evening_chart_goes_out_without_the_database(self):
        from alerts.telegram_paper import CAPTION_LIMIT
        state = {}
        utc = lambda hh, mm=31: datetime(2026, 10, 15, hh, mm)          # Tehran = UTC + 3:30
        self.assertEqual(self._evening(False, utc(16), state), ([], []), "before 21:00 nothing is asked or sent")
        sent, calls = self._evening(True, utc(17), state)                 # 21:01, the database up
        self.assertEqual(sent, [], "with the database up, PAPER's own report carries the chart")
        self.assertEqual(calls, ["checked"])
        sent, calls = self._evening(False, utc(17), state)                # 21:01, the database down
        self.assertEqual(len(sent), 1)
        text, png = sent[0]
        self.assertEqual(png[1:4], b"PNG", "the chart, drawn from tgju's own candles")
        self.assertIn(("TGJU_GOLD_18K", date(2026, 10, 15)), calls, "18K's candles before today")
        plain = re.sub(r"</?[bi]>", "", text)
        for part in ("GOLDPremium: EVENING", "23 Mehr 1405, 21:00", "18K ", "the 20-day average (yesterday", "the 50-day",
                     " channel, ", "GOLD FUNDS · individuals, last 10 sessions (tablokhani)",
                     "The room's report returns with the database"):
            self.assertIn(part, plain)
        for char in "<>&":
            self.assertNotIn(char, plain)
        self.assertLessEqual(len(plain), CAPTION_LIMIT, "it fits under the chart")
        self.assertEqual(state["evening_fallback_date"], "2026-10-15")
        self.assertEqual(self._evening(False, utc(18), state), ([], []), "once a Tehran day")

    def test_36_tgju_direct_has_the_stored_candles_shape(self):
        import collector.tgju as tg
        from persistence import candle_cache as cc
        served = [  # newest first, as tgju serves them
            {"date": "2026-10-15", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},      # today: incomplete
            {"date": "2026-10-14", "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0},
            {"date": "2026-10-14", "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0},   # served twice
            {"date": "2026-10-13", "open": 10.0, "high": 9.0, "low": 9.5, "close": 10.0},    # stored, flagged
            {"date": "2026-10-12", "open": None, "high": 9.0, "low": 9.0, "close": 9.0},     # not a candle
            {"date": "2026-10-11", "open": 8.0, "high": 9.0, "low": 7.0, "close": 8.5}]
        asked, real = [], tg.fetch_daily_candles
        tg.fetch_daily_candles = lambda key, rows, start=0, order="desc": asked.append((key, rows, order)) or served
        try:
            got = cc.direct("TGJU_GOLD_18K", date(2026, 10, 15))
        finally:
            tg.fetch_daily_candles = real
        self.assertEqual(asked, [("geram18", 1000, "desc")], "one request, measured to match the full history")
        self.assertEqual([(c.trade_date.isoformat(), c.source_quality) for c in got],
                         [("2026-10-11", "COMPLETE"), ("2026-10-13", "INCONSISTENT"), ("2026-10-14", "COMPLETE")])

    def test_37_only_the_evening_chart_reads_tgju_directly(self):
        # the room and the quant engine replay the whole history: fed 1,000 days they would
        # silently decide on less, so the direct route stays with the chart
        import main
        users = []
        for root, _, files in os.walk(SRC_DIR):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(root, name), encoding="utf-8") as f:
                        if re.search(r"import[^\n]*\bdirect\b|candle_cache\.direct\(", f.read()):
                            users.append(name)
        self.assertEqual(users, ["main.py"])
        self.assertEqual(inspect.getsource(main).count("import direct"), 1)
        self.assertIn("import direct", inspect.getsource(main._evening_fallback))

    def test_38_the_evening_caption(self):
        from alerts.telegram_paper import build_evening_message
        reading = {"price": 263_449_605.0, "live": True, "as_of": date(2026, 10, 14), "phase": "MARKUP",
                   "channel": {"slope_pct_day": 0.55, "position": 0.3}, "swing": (date(2026, 6, 16), 156_500_000.0, "L"),
                   "ema20": (0.8, -1.2), "ema50": (10.2, 9.0)}
        lines = re.sub(r"</?[bi]>", "", build_evening_message(date(2026, 10, 15), reading)).splitlines()
        self.assertEqual(lines, ["GOLDPremium: EVENING · 23 Mehr 1405, 21:00",
                                 "18K 26.34M (market, tgju) · rising, up from 15.65M on 26 Khordad",
                                 "Rising channel, +0.55% a day; price in its lower half",
                                 "0.8% above the 20-day average (yesterday 1.2% below), 10% above the 50-day",
                                 "",
                                 "The room's report returns with the database"])
        bare = build_evening_message(date(2026, 10, 15), None)
        self.assertIn("Chart reading: not enough history", bare)
        # the locked layout of 2026-10-17 (SP_D_HANDOFF.md section 47): the funds' block, then the expected return
        full = build_evening_message(date(2026, 10, 15), reading, ["<b>GOLD FUNDS</b> · individuals, x"], date(2026, 11, 1))
        self.assertTrue(full.endswith("GOLD FUNDS</b> · individuals, x\n\nThe room's report returns with the database "
                                      "(expected 10 Aban)"), full)


    # -- the pattern reader (SP_D_HANDOFF.md sections 37.4-37.5) ----------------------------

    def _rally_range_breakout(self):
        """A sharp rally of 20% over 5 days (the pole), a range of 10 days within 2%, then a close 8% above it:
        a range grows while every close stays within 6% of the others, so a breakout leaves that band.
        A slower rally lets the range absorb its last days, and the reader rightly calls it a plain breakout."""
        c = [100.0 * 1.001 ** k for k in range(120)]
        for k in range(5):
            c.append(c[-1] * 1.038)
        top = c[-1]
        for k in range(10):
            c.append(top * (0.985 if k % 2 else 0.995))
        c.append(top * 1.08)
        dates = [date(2025, 1, 1) + timedelta(days=k) for k in range(len(c))]
        return dates, [x * 1.004 for x in c], [x * 0.996 for x in c], c

    def test_39_the_reader_finds_the_range_the_flag_and_the_ema_test(self):
        import numpy as np
        from caluclator import patterns as pt
        dates, h, l, c = self._rally_range_breakout()
        r = pt.read(dates, h, l, c)
        kinds = [e[1] for e in r["events"]]
        self.assertIn("FLAG", kinds, "a pole of 15% and a range of at most half of it: a flag")
        self.assertIsNotNone(r["flag"], "its target is not reached yet: the flag is live")
        day, level, target, stop = r["flag"]
        self.assertEqual(day, dates[-1])
        self.assertGreater(target, c[-1], "the pole's height above the breakout")
        self.assertAlmostEqual(stop, pt.ranges(np.array(c))[-1][2], msg="invalid under the range's low")
        steep = np.array([100.0 * 1.01 ** k for k in range(150)])  # lows stay far above the lagging 20-day
        e20 = __import__("talib").EMA(steep, 20)
        k = 120
        lows = steep * 0.996
        lows[k] = e20[k] * 0.999                      # a dip to the 20-day that closes above it
        tests = pt.ema_tests(steep * 1.004, lows, steep)
        self.assertEqual([e[0] for e in tests], [k], "a low at the 20-day, a close above it, in an uptrend: an EMA20 test")

    def test_40_the_names_carry_no_forecast(self):
        from caluclator import patterns as pt
        self.assertEqual(pt.name("RISING WEDGE (down)"), "rising wedge")
        self.assertEqual(pt.name("FLAG"), "flag breakout")
        for kind, (hit, n, control) in pt.RECORD.items():
            self.assertLessEqual(hit, n)
            self.assertIn(kind, pt.POINTS, "the caption says where the books expect it to go")
        self.assertEqual(pt.RECORD["FLAG"], pt.FLAG_RECORD)

    def test_41_the_chart_and_the_evening_caption_carry_the_reading(self):
        import main
        import alerts.chart as chart
        from alerts.telegram_paper import pattern_lines
        from persistence.candle_cache import Candle
        dates, h, l, c = self._rally_range_breakout()
        dates = [date(2025, 1, 1) + timedelta(days=k) for k in range(len(c) + 200)][-len(c):]
        rows = [Candle(d_, x, hh, ll, x, "COMPLETE") for d_, hh, ll, x in zip(dates, h, l, c)]
        rows = [Candle(dates[0] - timedelta(days=200 - k), c[0], h[0], l[0], c[0], "COMPLETE") for k in range(200)] + rows
        seen, real = {}, chart.render
        chart.render = lambda *a, **k: seen.update(k) or b"\x89PNG"
        try:
            with redirect_stdout(io.StringIO()):
                png = main._chart_png(rows, (), c[-1], "18K daily")
        finally:
            chart.render = real
        self.assertEqual(png, b"\x89PNG")
        self.assertTrue(seen["patterns"]["boxes"], "the range is drawn")
        self.assertIn("flag target", [t[1] for t in seen["patterns"]["targets"]])
        self.assertIn("trend", seen, "and everything the chart drew before (owner: both worlds)")
        found = main._evening_reading(rows, c[-1])["patterns"]
        lines = pattern_lines(found)
        self.assertTrue(any(x.startswith("Flag of ") for x in lines))
        self.assertIn("past flags got there within 2 months", "\n".join(lines))

    def _week_demand(self):
        """gold_demand.assess's reading of the 7 days to 2026-10-03 as the old seed gave it, fixed here so the
        layout is checked apart from the seed, which is refreshed (section 48)."""
        return {"as_of": "2026-10-03", "window": 7, "net_rial": 113_277_138_687_149.0, "buyers_per_day": 86_414.29,
                "usual_rial": 21_178_567_232_895.0, "band": [-2.78, 4.93], "per_head_rial": [1_620_399_514.0, 2_835_609_471.0],
                "money": {"value": 5.3487, "rank": 92.4, "state": "HIGH"},
                "people": {"value": 1.6736, "rank": 91.2, "state": "HIGH"},
                "size": {"value": 0.5714, "rank": 32.4, "state": "NORMAL"}}

    def test_42_the_room_report_has_the_funds_block_not_the_range(self):
        from alerts.telegram_paper import build_room_report_message, demand_block
        view = {"posture": "ALL_GOLD", "reasons": [], "next_review": "2026-10-19", "members": {}, "for_fixed_income": [],
                "for_gold": [], "band20": [240_000_000, 290_000_000, 230_000_000, 300_000_000, 265_000_000]}
        demand = self._week_demand()
        args = (DAY, "Goldika", SELL, "", 3, 0.0, None, False, 3 * SELL, p.START_CASH_IRR, DAY, None, [], view)
        plain = re.sub(r"</?[bi]>", "", build_room_report_message(*args, demand=demand))
        self.assertNotIn("Next 20 trading days", plain, "the range gives nothing to decide on (owner, 2026-10-16)")
        # the block of the evening's locked preview (owner, 2026-10-17; SP_D_HANDOFF.md sections 46-47)
        self.assertIn("GOLD FUNDS · individuals, 7 days to 11 Mehr\n"
                      "Money: 11,328B toman in, 5.3 times the usual week; above the normal range (up to 4.9 times)\n"
                      "Buyers: 86,414 a day, 1.7 times the usual; a rush\n"
                      "Per head: buyers 162M, sellers 284M toman (sellers bigger, as usual)", plain)
        stale = dict(demand, as_of="2026-09-20")
        self.assertEqual(demand_block(stale, DAY), [], "a reading more than a week old is left out")
        self.assertNotIn("GOLD FUNDS", re.sub(r"</?[bi]>", "", build_room_report_message(*args)))

    def test_43_the_stand_in_reads_the_seeds_funds_from_tablokhani(self):
        """While the database, and with it the phone's days, is out of reach, the evening's funds come from
        tablokhani's 10-day averages over the seed's 18 funds, read against the seed (owner, 2026-10-17)."""
        import main
        from collector import tablokhani as tk
        from analysis import gold_demand
        node = open(os.path.join(SRC_DIR, "..", "iran_node", "node.py"), encoding="utf-8").read()
        listed = re.search(r"GOLD_FUNDS = \((.*?)\)\n\n", node, re.S).group(1)
        phone = {s.replace("ي", "ی").replace("ك", "ک") for s in re.findall(r'"\d+", "([^"]+)"', listed)} - {"سافرون"}
        self.assertEqual(set(tk.GOLD_FUNDS), phone, "tablokhani's list is the seed's and the phone's 18 funds")
        flows = {s: (1e12, 4_000.0, 0.9e12, 2_000.0) for s in tk.GOLD_FUNDS}
        dm = main._tablokhani_demand(flows)
        self.assertEqual((dm["window"], dm["as_of"]), (10, None), "10 sessions, no date of its own")
        n = len(tk.GOLD_FUNDS)
        self.assertEqual(n, 19, "the seed's 18 and گنج (section 48)")
        self.assertAlmostEqual(dm["net_rial"], n * 0.1e12 * 10)
        self.assertAlmostEqual(dm["buyers_per_day"], n * 4_000.0)
        self.assertEqual(main._tablokhani_demand(dict(list(flows.items())[:gold_demand.MIN_FUNDS - 1])), {})
        from alerts.gold_funds import block
        lines = block(dm, title="last 10 sessions (tablokhani)")
        self.assertEqual(re.sub(r"</?[bi]>", "", lines[0]), "GOLD FUNDS · individuals, last 10 sessions (tablokhani)")
        self.assertIn("times the usual 10 sessions", lines[1])

    def test_44_only_the_patterns_that_worked_on_18k_are_shown(self):
        """The rising wedge reached its target 2 times in 41, the double top 3 in 12: the books' reading is not
        shown (owner, 2026-10-17). A box is shown with the road out of each side and its record."""
        from alerts.telegram_paper import SHOWN, odds, pattern_lines
        from caluclator.patterns import RECORD
        d = lambda k: date(2026, 10, k)
        found = {"ranges": [(d(1), d(15), 252_700_000.0, 267_400_000.0, True)], "tests": [d(13)], "flag": None,
                 "events": [(d(3), "RISING WEDGE (down)", 260e6, 240e6, 270e6),
                            (d(4), "DOUBLE TOP (down)", 260e6, 240e6, 270e6),
                            (d(5), "DOUBLE BOTTOM (up)", 255e6, 275e6, 245e6)]}
        lines = pattern_lines(found)
        text = "\n".join(lines)
        self.assertNotIn("wedge", text.lower())
        self.assertNotIn("double top", text.lower())
        self.assertIn("Double bottom on 13 Mehr: opens the road to 27.50M", text)
        self.assertEqual(lines[:4], [
            "Touched the 20-day average on 21 Mehr and bounced (after such bounces the next month was a little "
            "stronger than usual)",
            "In a box since 9 Mehr, 25.27M to 26.74M",
            "  Close above 26.74M: opens the road to 28.21M (3 in 4 got there)",
            "  Close below 25.27M: may lead to 23.80M (about half got there)"])
        hidden = {kind for kind, (hit, n, _c) in RECORD.items() if hit / n <= SHOWN}
        self.assertEqual(hidden, {"RISING WEDGE", "DOUBLE TOP", "FALLING WEDGE"})
        self.assertEqual((odds(30, 39), odds(12, 22)), ("3 in 4", "about half"))

    def test_46_the_chart_is_drawn_without_a_live_price(self):
        """With every platform down there is no live price; the levels split at the last close (section 48)."""
        import main
        import alerts.chart as chart
        from persistence.candle_cache import Candle
        dates, h, l, c = self._rally_range_breakout()
        rows = [Candle(date(2024, 1, 1) + timedelta(days=k), x, hh, ll, x, "COMPLETE")
                for k, (hh, ll, x) in enumerate(zip([h[0]] * 200 + h, [l[0]] * 200 + l, [c[0]] * 200 + c))]
        seen, real = {}, chart.render
        chart.render = lambda *a, **k: seen.update(k) or b"\x89PNG"
        try:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main._chart_png(rows, (), None, "18K daily"), b"\x89PNG")
        finally:
            chart.render = real
        self.assertIsNone(seen["live"])

    def test_47_the_chart_draws_the_longer_tested_line_beside_the_closest(self):
        """Option C (owner, 2026-10-18; SP_D_HANDOFF.md 48.3): the most-touched resistance line, from 3 touches,
        thin and dashed beside the closest one. The chart's pattern marks follow the caption's rule."""
        import numpy as np
        import main
        from caluclator import patterns
        from caluclator.technical import trendlines
        n = 120
        c = 100 + 0.5 * np.arange(n)
        h, l = c * 1.004, c * 0.996
        for k in (20, 40, 60, 80):                           # four swing highs on one long line
            h[k] = 105 + 0.5 * k
        h[100], h[110] = 156.5, 160.0                        # a later pair: the closer line; 110 also on the long one
        t = trendlines(h, l, c, upto=n - 1)
        self.assertEqual((t["resistance_tested"]["i1"], t["resistance_tested"]["touches"]), (20, 6),
                         "its four highs, and 100 and 110 within 1% of it")
        self.assertNotEqual(t["resistance"]["i1"], 20, "the closest line is another one")
        self.assertLess(t["resistance"]["at"], t["resistance_tested"]["at"])
        h2 = c * 1.004
        h2[100], h2[110] = 156.5, 160.0
        self.assertIsNone(trendlines(h2, l, c, upto=n - 1)["resistance_tested"], "under 3 touches: not drawn")
        source = inspect.getsource(__import__("alerts.chart", fromlist=["render"]).render)
        self.assertIn('linestyle="--" if tested', source)
        self.assertIn("longer resistance line, touched", source)
        self.assertFalse(patterns.shown("RISING WEDGE (down)"))
        self.assertTrue(patterns.shown("EMA20 TEST") and patterns.shown("FLAG"))
        for unrated in ("HEAD AND SHOULDERS", "SYMMETRICAL TRIANGLE", "TRIPLE TOP (down)"):
            self.assertFalse(patterns.shown(unrated), f"{unrated}: too few cases on 18K to rate")
        self.assertIn("patterns.shown(kind)", inspect.getsource(main._pattern_overlay))

    def test_45_the_evening_keeps_its_chart_when_the_funds_make_it_too_long(self):
        import main
        import alerts.telegram_paper as tp
        import persistence.candle_cache as cc
        from collector import tablokhani as tk
        reading = {"price": 262_600_000.0, "live": False, "as_of": date(2026, 10, 15), "phase": "MARKUP", "patterns": None,
                   "channel": {"slope_pct_day": 0.55, "position": 0.3}, "swing": (date(2026, 6, 16), 156_500_000.0, "L"),
                   "ema20": (2.7, 2.2), "ema50": (10.2, 9.0)}
        sent = []
        real = (main._database_reachable, main._chart_png, main._evening_reading, cc.direct, tk.collect,
                tp.send_paper_report, tp.send_paper, tp.CAPTION_LIMIT)
        try:
            main._database_reachable = lambda: False
            main._chart_png = lambda *a, **k: b"PNG"
            main._evening_reading = lambda rows, live: reading
            cc.direct = lambda *a, **k: [__import__("types").SimpleNamespace(trade_date=date(2026, 10, 15))]
            tk.collect = lambda: {"flows": {s: (1e12, 4_000.0, 0.9e12, 2_000.0) for s in tk.GOLD_FUNDS}}
            tp.send_paper_report = lambda text, png=None: sent.append(("chart", text))
            tp.send_paper = lambda text: sent.append(("text", text))
            state = {"service": {"database": {"last": {"reason": "exceeded the data transfer quota"}}}}
            now = datetime(2026, 10, 17, 17, 40)                          # 21:10 Tehran
            with redirect_stdout(io.StringIO()):
                main._evening_fallback({}, now, dict(state))
            self.assertEqual([k for k, _ in sent], ["chart"])
            self.assertIn("GOLD FUNDS</b> · individuals, last 10 sessions (tablokhani)", sent[0][1])
            self.assertIn("(expected 10 Aban)", sent[0][1])
            sent.clear()
            tp.CAPTION_LIMIT = 300
            with redirect_stdout(io.StringIO()):
                main._evening_fallback({}, now, dict(state))
            self.assertEqual([k for k, _ in sent], ["chart", "text"], "the chart is kept; the funds follow on their own")
            self.assertNotIn("GOLD FUNDS", sent[0][1])
            self.assertTrue(sent[1][1].startswith("<b>GOLD FUNDS</b>"))
        finally:
            (main._database_reachable, main._chart_png, main._evening_reading, cc.direct, tk.collect,
             tp.send_paper_report, tp.send_paper, tp.CAPTION_LIMIT) = real


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
