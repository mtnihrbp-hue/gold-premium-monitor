"""KPI: the one nightly message (SP_D_HANDOFF.md 104.5, 105.4, 106.3, 109).

The numbers (analysis/nightly), their words (alerts/telegram_nightly), the record written before the outcome and judged
on the same series, a pull that writes nothing, and the switch that replaces the PAPER report's text, the LENS and the
evening's fallback.

    python kpi/kpi_nightly.py
"""

import math
import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.environ.pop("DATABASE_URL", None)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from alerts import telegram_nightly as tn  # noqa: E402
from alerts import telegram_pulse  # noqa: E402
from analysis import nightly  # noqa: E402
from database import repository as repo  # noqa: E402
from database.models import Base, MarketSnapshot, NightlyForecast, PlatformPrice  # noqa: E402

TUESDAY = date(2026, 11, 10)          # 19 Aban: Sat 11-07, Sun 11-08 and Mon 11-09 are its week's sessions
WEDNESDAY = date(2026, 11, 11)
THURSDAY = date(2026, 11, 12)         # the week of 11-07 has closed: five sessions read
SIGMA = 0.014


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def flows_for(today, this_week=(1000, 100, 2000, 100), weeks=60):
    """A year and more of ordinary fund weeks of five sessions, and this week's sessions up to yesterday."""
    out = {}
    start = nightly.week_of(today)
    for w in range(1, weeks + 1):
        for s in range(5):
            day = start - timedelta(days=7 * w) + timedelta(days=s)
            out[day] = [1000.0 + w * 3, 100.0, 1000.0, 100.0 + (w % 7)]
    for s in range((today - start).days):
        day = start + timedelta(days=s)
        if day.weekday() not in nightly.FUND_DAYS:
            continue
        out[day] = list(map(float, this_week))
    return out


def market(price=251577090.0):
    return {"ref_date": "2026-11-09", "price": price, "world": 4073.0, "usd": 2608000.0, "tether": 2647860.0,
            "price_pct": -1.5, "world_pct": -1.7, "usd_pct": -1.2, "tether_pct": 0.0, "tether_record": False,
            "gap_now": -2.0, "gap_then": -3.0}


def view(funds=None, pull=False, at=None, three=True, zone=None):
    v = {"at": at or datetime(2026, 11, 10, 21, 0), "market": market(), "discount": {"now": -2.1, "then": -3.1, "index": "WallGold"},
         "three_day": nightly.three_day_line(251577090.0, SIGMA, zone) if three else None,
         "funds": funds, "room": {"total": 1276917803.0, "afran": 524491240.0, "gold": 752420190.0, "grams": 3, "since": "2026-11-01"},
         "pull": pull, "odds": [], "news": None, "headlines": 0}
    v["funds_line"] = nightly.funds_line(funds, v["three_day"])
    return v


class TheNumbers(unittest.TestCase):
    def test_01_friday_is_not_a_trading_night(self):
        self.assertEqual(nightly.trading_nights_after(date(2026, 11, 8), 3), date(2026, 11, 11))     # Sunday to Wednesday (106.3)
        self.assertEqual(nightly.trading_nights_after(TUESDAY, 3), date(2026, 11, 14))               # over the Friday

    def test_02_the_low_edge_is_the_three_day_range(self):
        t = nightly.three_day_line(250_000_000.0, SIGMA, None)
        self.assertAlmostEqual(t["floor"], 250_000_000.0 * math.exp(-1.11 * SIGMA * math.sqrt(3)))
        self.assertAlmostEqual(t["high"], 250_000_000.0 * math.exp(1.89 * SIGMA * math.sqrt(3)))
        self.assertLess(t["floor_pct"], 0)
        self.assertGreater(t["high_pct"], 0)

    def test_03_the_chance_is_the_record_by_zone(self):
        for zone, chance in (("SELLERS", 58), ("BUYERS", 61), ("CROWDED", 57), (None, 60)):
            self.assertEqual(nightly.three_day_line(1e8, SIGMA, zone)["chance_higher"], chance)
            self.assertEqual(nightly.three_day_line(1e8, SIGMA, zone)["chance_above"], 90)

    def test_04_no_base_or_volatility_no_line(self):
        self.assertIsNone(nightly.three_day_line(None, SIGMA, None))
        self.assertIsNone(nightly.three_day_line(1e8, None, None))

    def test_05_the_fund_week_opens_on_saturday(self):
        self.assertEqual(nightly.week_of(date(2026, 11, 7)), date(2026, 11, 7))
        self.assertEqual(nightly.week_of(TUESDAY), date(2026, 11, 7))
        self.assertEqual(nightly.week_of(date(2026, 11, 13)), date(2026, 11, 7))      # Friday: still that week

    def test_06_under_three_sessions_no_zone(self):
        f = nightly.funds_view(flows_for(date(2026, 11, 8)), date(2026, 11, 8))     # Sunday, Saturday read
        self.assertEqual(f["n"], 1)
        self.assertIsNone(f["zone"])
        self.assertIsNone(nightly.funds_line(f, nightly.three_day_line(1e8, SIGMA, None)))
        self.assertTrue(f["today_missing"])

    def test_07_a_week_of_big_sellers_is_sellers(self):
        f = nightly.funds_view(flows_for(THURSDAY, this_week=(1000, 400, 4000, 100)), THURSDAY)
        self.assertEqual(f["n"], 5)
        self.assertEqual(f["zone"], "SELLERS")
        self.assertLess(f["buy_head"], f["sell_head"])

    def test_08_a_week_of_big_buyers_ranks_high(self):
        f = nightly.funds_view(flows_for(THURSDAY, this_week=(9000, 100, 1000, 400)), THURSDAY)
        self.assertEqual(f["zone"], "CROWDED")

    def test_09_the_chance_uses_the_week_that_ended(self):
        # a week in progress has not ended: the 3-day chance reads the one before, as the record was measured (102.1)
        f = nightly.funds_view(flows_for(TUESDAY, this_week=(1000, 400, 4000, 100)), TUESDAY)
        self.assertEqual(f["chance_zone"], f["last_zone"])
        thursday = date(2026, 11, 12)
        g = nightly.funds_view(flows_for(thursday, this_week=(1000, 400, 4000, 100)), thursday)
        self.assertEqual(g["chance_zone"], g["zone"])
        self.assertTrue(g["finished"])

    def test_10_the_line_takes_the_records_rates(self):
        three = nightly.three_day_line(1e8, SIGMA, None)
        for zone, lower, side, chance in (("SELLERS", 46, "drop", 25), ("BUYERS", 29, "rise", 30), ("CROWDED", 42, "drop", 23)):
            line = nightly.funds_line({"zone": zone}, three)
            self.assertEqual((line["lower"], line["side"], line["chance"]), (lower, side, chance))
            self.assertEqual(line["level"], three["floor"] if side == "drop" else three["high"])


    def test_10b_a_week_not_yet_closed_has_no_line(self):
        """On the third session the record's 46% is 36%, below any week's (SP_D_HANDOFF.md 111.1): no zone, no line."""
        f = nightly.funds_view(flows_for(TUESDAY, this_week=(1000, 400, 4000, 100)), TUESDAY)
        self.assertEqual(f["n"], 3)
        self.assertFalse(f["closed"])
        self.assertIsNone(f["zone"])
        self.assertIsNone(nightly.funds_line(f, nightly.three_day_line(1e8, SIGMA, None)))
        text = " ".join(tn._funds(view(f)))
        self.assertIn("this week so far", text)
        self.assertIn("Too early to call this week.", text)
        self.assertNotIn("to close lower", text)

    def test_10c_wednesday_needs_its_own_session(self):
        flows = flows_for(WEDNESDAY, this_week=(1000, 400, 4000, 100))
        f = nightly.funds_view(flows, WEDNESDAY)
        self.assertFalse(f["closed"])
        self.assertIsNone(f["zone"])
        self.assertTrue(f["today_missing"])
        flows[WEDNESDAY] = [1000.0, 400.0, 4000.0, 100.0]
        g = nightly.funds_view(flows, WEDNESDAY)
        self.assertTrue(g["closed"])
        self.assertEqual((g["n"], g["zone"]), (5, "SELLERS"))
        text = " ".join(tn._funds(view(g)))
        self.assertIn("this week, Sat", text)
        self.assertIn("46% to close lower (typical 38%)", text)

    def test_10d_the_chance_still_reads_the_week_before_on_wednesday(self):
        flows = flows_for(WEDNESDAY, this_week=(1000, 400, 4000, 100))
        flows[WEDNESDAY] = [1000.0, 400.0, 4000.0, 100.0]
        g = nightly.funds_view(flows, WEDNESDAY)
        self.assertEqual(g["chance_zone"], g["last_zone"])         # 102.1: the last fund week that ended before the day


class TheWords(unittest.TestCase):
    def test_11_the_locked_shape(self):
        text = tn.build_nightly_message(view(nightly.funds_view(flows_for(TUESDAY, (1000, 400, 4000, 100)), TUESDAY)))
        order = [text.index(x) for x in ("GOLDPremium: NIGHT", "<b>NOW</b> vs the close of 18 Aban", "<b>NEXT 3 DAYS</b>",
                                         "<b>GOLD FUNDS</b>", "<b>THE EVENT</b>", "<b>THE ROOM</b> (PAPER)", "Decision support")]
        self.assertEqual(order, sorted(order))
        self.assertIn("18K 25.16M (market, tgju): −1.5%", text)
        self.assertIn("vs tonight's 25.16M", text)
        self.assertIn("to close above 24.", text)
        self.assertIn("Discount 2.1% below world price (was 3.1% below at the close of 18 Aban)", text)
        self.assertIn("75.2M toman in gold (3 g), 52.4M in Afran (fixed income) since 10 Aban · total 127.7M", text)
        self.assertNotIn("Early look", text)

    def test_12_a_pull_says_so_and_now(self):
        early = tn.build_nightly_message(view(pull=True, at=datetime(2026, 11, 10, 17, 5)))
        self.assertIn(tn.EARLY.replace("<i>", "").replace("</i>", ""), early)
        self.assertIn("vs 25.16M now", early)
        late = tn.build_nightly_message(view(pull=True, at=datetime(2026, 11, 10, 22, 5)))
        self.assertIn("These numbers are from now.", late)

    def test_13_what_cannot_be_read_says_unknown(self):
        v = view(three=False)
        v["room"] = None
        text = tn.build_nightly_message(v)
        self.assertEqual(text.count("Unknown tonight."), 3)            # the 3-day line, the funds, the room

    def test_14_no_index_no_discount(self):
        v = view()
        v["discount"] = {"now": None, "then": -3.1, "index": "WallGold"}
        self.assertIn("Discount not read (WallGold)", tn.build_nightly_message(v))

    def test_15_too_early_names_last_week(self):
        sunday = date(2026, 11, 8)
        f = nightly.funds_view(flows_for(sunday), sunday)
        f["last_zone"] = "SELLERS"
        text = "\n".join(tn._funds(view(f)))
        self.assertIn("Too early to call this week. Last week (", text)
        self.assertIn("big holders among them were selling", text)
        self.assertIn("Sunday's not read yet", text)

    def test_16_the_vocabulary(self):
        text = tn.build_nightly_message(view(nightly.funds_view(flows_for(TUESDAY, (1000, 400, 4000, 100)), TUESDAY)))
        for word in ("dip", "stall", "median", "cheap", "BUY", "SELL"):
            self.assertNotRegex(text, rf"\b{word}\b")
        self.assertTrue(text.endswith("<i>Decision support, not an instruction to trade.</i>"))
        self.assertEqual(set(re.findall(r"</?([a-z]+)>", text)), {"b", "i"})

    def test_17_one_session_and_the_full_week_read_right(self):
        sunday = date(2026, 11, 8)
        one = tn._money(dict(nightly.funds_view(flows_for(sunday), sunday), usual_net=4.2e12, net=-3.17e12))
        self.assertEqual(one, "Money: individuals took out 317B toman; a usual first session brings 420B in")
        two = tn._money({"net": 1e12, "n": 3, "usual_net": -1e12})
        self.assertEqual(two, "Money: individuals put in 100B toman; the usual first 3 sessions take 100B out")
        five = tn._money({"net": 1e12, "n": 5, "usual_net": 2e12})
        self.assertEqual(five, "Money: individuals put in 100B toman; a usual week brings 200B in")


    def test_17b_a_long_night_is_cut_between_blocks(self):
        text = "\n\n".join(["<b>A</b>\n" + "x" * 1800, "<b>B</b>\n" + "y" * 1800, "<b>C</b>\n" + "z" * 1800])
        pieces = tn.parts(text)
        self.assertEqual(len(pieces), 2)
        self.assertTrue(all(len(p) <= tn.MESSAGE_LIMIT for p in pieces))
        self.assertEqual("\n\n".join(pieces), text)
        self.assertEqual(tn.parts("short"), ["short"])


class TheRecord(unittest.TestCase):
    def rows(self, day=THURSDAY):
        f = nightly.funds_view(flows_for(day, (1000, 400, 4000, 100)), day)
        return nightly.forecast_rows(day, view(f), datetime(2026, 11, 12, 17, 30))

    def test_18_the_message_commits_to_two_rows(self):
        rows = self.rows()
        self.assertEqual([r["forecaster"] for r in rows], ["three_day", "funds_week"])
        self.assertEqual(rows[0]["due_date"], date(2026, 11, 16))         # over the Friday (106.3)
        self.assertEqual(rows[1]["due_date"], date(2026, 11, 18))         # 7 days after the week's last session (100.3)

    def test_18b_a_week_not_yet_closed_commits_only_to_the_three_days(self):
        f = nightly.funds_view(flows_for(TUESDAY, (1000, 400, 4000, 100)), TUESDAY)
        rows = nightly.forecast_rows(TUESDAY, view(f), datetime(2026, 11, 10, 17, 30))
        self.assertEqual([r["forecaster"] for r in rows], ["three_day"])

    def test_19_no_line_no_row(self):
        self.assertEqual(nightly.forecast_rows(TUESDAY, view(three=False), datetime(2026, 11, 10, 17, 30)), [])

    def test_20_a_day_is_written_once(self):
        s = session()
        row = self.rows()[0]
        self.assertTrue(repo.save_nightly_forecast(s, **row))
        self.assertFalse(repo.save_nightly_forecast(s, **dict(row, base_price=999.0)))
        self.assertEqual(s.query(NightlyForecast).count(), 1)
        self.assertEqual(float(s.query(NightlyForecast).one().base_price), 251577090.0)

    def test_20b_the_funds_line_is_kept_once_a_week(self):
        s = session()
        row = self.rows()[1]
        self.assertTrue(repo.save_nightly_forecast(s, **dict(row, local_date=WEDNESDAY)))
        self.assertFalse(repo.save_nightly_forecast(s, **row), "Thursday: the week already has its row")
        self.assertFalse(repo.save_nightly_forecast(s, **dict(row, local_date=date(2026, 11, 13))), "nor Friday")
        self.assertTrue(repo.save_nightly_forecast(s, **dict(row, local_date=date(2026, 11, 18))), "the next week has its own")
        self.assertEqual(s.query(NightlyForecast).count(), 2)

    def test_21_due_rows_only_and_once(self):
        s = session()
        for row in self.rows():
            repo.save_nightly_forecast(s, **row)
        self.assertEqual(repo.due_nightly_forecasts(s, date(2026, 11, 15)), [])
        due = repo.due_nightly_forecasts(s, date(2026, 11, 16))
        self.assertEqual([r.forecaster for r in due], ["three_day"])
        due[0].resolved_at = datetime(2026, 11, 16, 17, 30)
        s.commit()
        self.assertEqual(repo.due_nightly_forecasts(s, date(2026, 11, 16)), [])

    def test_22_judged_on_the_same_series(self):
        out = nightly.score("three_day", 100.0, {"floor": 97.0}, 101.0, {date(2026, 11, 14): 101.0})
        self.assertTrue(out["higher"] and out["above_floor"])
        self.assertAlmostEqual(out["change_pct"], 1.0)
        out = nightly.score("three_day", 100.0, {"floor": 97.0}, 96.0, {})
        self.assertFalse(out["higher"] or out["above_floor"])

    def test_23_the_week_counts_any_night_at_the_level(self):
        nights = {date(2026, 11, 11): 99.0, date(2026, 11, 12): 96.5, date(2026, 11, 14): 101.0}
        out = nightly.score("funds_week", 100.0, {"side": "drop", "level": 97.0}, 101.0, nights)
        self.assertTrue(out["reached"])
        self.assertFalse(out["lower"])
        self.assertEqual(out["nights"], 3)
        out = nightly.score("funds_week", 100.0, {"side": "rise", "level": 105.0}, 101.0, nights)
        self.assertFalse(out["reached"])

    def test_24_the_nights_come_from_the_three_day_rows(self):
        s = session()
        for d, base in ((date(2026, 11, 10), 100.0), (date(2026, 11, 11), 101.0), (date(2026, 11, 12), 102.0)):
            repo.save_nightly_forecast(s, local_date=d, forecaster="three_day", version="v1", recorded_at=datetime(2026, 11, 10),
                                       base_price=base, due_date=d + timedelta(days=4), forecast={"floor": 1.0})
        self.assertEqual(repo.nightly_prices(s, date(2026, 11, 10), date(2026, 11, 12)),
                         {date(2026, 11, 11): 101.0, date(2026, 11, 12): 102.0})

    def test_25_a_held_forecast_goes_back(self):
        import json
        from persistence import spool
        row = self.rows()[0]
        decoded = json.loads(json.dumps(row, default=spool._encode), object_hook=spool._decode)
        self.assertEqual(decoded, row)
        s = session()
        writers = repo.spool_writers(s, [{"kind": "forecast", "payload": row}])
        writers["forecast"](s, row)
        writers["forecast"](s, row)
        s.commit()
        self.assertEqual(s.query(NightlyForecast).count(), 1)

    def test_26_the_discount_then_is_the_index_at_the_days_last_reading(self):
        s = session()
        for hour, wall, fair in ((14, 96.0, 100.0), (17, 97.0, 100.0)):           # UTC: both on 18 Aban (11-09) in Tehran
            snap = MarketSnapshot(timestamp=datetime(2026, 11, 9, hour, 30), fair_price=fair, premium_percent=-3.0,
                                  world_gold_usd=4000, usd_irr=260000, signal="WAIT", collection_mode="scheduled")
            s.add(snap)
            s.flush()
            s.add(PlatformPrice(snapshot_id=snap.id, platform_name="WallGold", price_irr=wall, timestamp=snap.timestamp))
            s.add(PlatformPrice(snapshot_id=snap.id, platform_name="Milli", price_irr=50.0, timestamp=snap.timestamp))
        s.commit()
        self.assertAlmostEqual(repo.index_gap_on(s, date(2026, 11, 9), "WallGold"), -3.0)
        self.assertIsNone(repo.index_gap_on(s, date(2026, 11, 8), "WallGold"))


class TheSwitch(unittest.TestCase):
    def source(self):
        with open(os.path.join(ROOT, "src", "main.py"), encoding="utf-8") as f:
            return f.read()

    def test_27_a_pull_writes_nothing(self):
        src = self.source()
        body = src[src.index("def _send_nightly_pull"):src.index("def _send_direction_report")]
        for name in ("save_", "_record_nightly", "spool.hold", "state["):
            self.assertNotIn(name, body, name)

    def test_28_the_breakout_push_is_the_flag_only(self):
        self.assertEqual(telegram_pulse.PUSHED, ("FLAG",))
        self.assertIn("kind not in PUSHED", self.source())

    def test_29_the_switch_replaces_the_old_messages(self):
        src = self.source()
        part = src[src.index("if _nightly_on(config):\n            _nightly_run"):]
        self.assertIn("_evening_fallback(markets, now, state)", part[:220])
        self.assertIn("_lens_run(markets, world, usd, now, state, config)", part[:260])

    def test_29b_the_report_keeps_its_rows_and_sends_the_chart_alone(self):
        src = self.source()
        body = src[src.index("def _paper_report"):src.index("def _usable")]
        self.assertLess(body.index('kind="REPORT"'), body.index("if _nightly_on():"))
        self.assertLess(body.index("if _nightly_on():"), body.index("send_paper_report(text, png)"))
        self.assertIn("_send_photo(png,", body)

    def test_30_the_record_is_on_the_write_back_list(self):
        import json
        import main
        self.assertIn("forecast", main.WRITE_BACK_KINDS)
        with open(os.path.join(ROOT, "config", "config.json"), encoding="utf-8") as f:
            self.assertIn("forecast", json.load(f)["spool"]["write_back"])

    def test_31_nothing_compares_a_rounded_threshold(self):
        with open(os.path.join(ROOT, "src", "analysis", "nightly.py"), encoding="utf-8") as f:
            self.assertNotIn("round(", f.read())


if __name__ == "__main__":
    unittest.main(verbosity=1)
