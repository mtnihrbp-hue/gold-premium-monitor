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

    def test_24_the_room_is_seven_members_and_plain_words(self):
        from analysis import room
        self.assertEqual(set(room.WEIGHTS), {"brake", "market state", "fair gap", "real dollar", "dollar 20d",
                                             "world gold 60d", "chartist"},
                         "money flow waits for TSETMC through the Iran-side collector")
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
                     "Next 20 trading days: most likely", "The room: 5 of 7 lean to fixed income, 1 to gold"):
            self.assertIn(part, plain)

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
