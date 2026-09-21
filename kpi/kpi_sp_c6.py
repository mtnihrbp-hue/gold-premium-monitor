"""KPI — SP-C.12: ANALYZE, and a push that interrupts without recommending.

ANALYZE answers the question UPDATE raises and never addresses: the discount is at
some level, and does that matter. It reports counts and ranks over readings that
already happened, and forecasts nothing.

The push exists for one measured reason. The deep zone typically stays open two hours
and its longest observed spell is five, so a reader who looks when they remember will
miss most of them. Nothing else the system knows justifies an interruption.

Four properties are load-bearing here:

- **The gate must fail open.** Its armed flag lives in state.json, carried between
  runs by the Actions cache -- the same cache whose loss latched last_alert into a
  permanent WAIT and suppressed 100 consecutive BUY candidates. Unknown state means
  armed. A lost cache costs a duplicate message; the opposite costs silence, which
  nothing alerts on and which this project has already paid for once.
- **The band must suppress flicker.** Firing on a bare threshold crossing produced
  four alerts in 41 hours for one episode on 8-9 August 2026, two of them 35 minutes
  apart. test_10 replays those readings.
- **Neither surface may recommend.** skills/telegram-product.md reserves external
  BUY/SELL alerts to the deterministic final_decision. A push that reads as advice
  takes that authority without holding it.
- **A report must not write.** skills/telegram-product.md: a user request must not
  silently become an Analysis Wing execution or historical learning observation.
"""

import inspect
import os
import sys
import unittest
from datetime import datetime, timedelta

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database.connection as db_conn

_TEST_ENGINE = create_engine("sqlite:///:memory:", echo=False)
_TestSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_TEST_ENGINE, expire_on_commit=False
)


def _test_get_session():
    return _TestSessionLocal()


db_conn.get_session = _test_get_session

from database.models import Base, MarketSnapshot, PlatformPrice
Base.metadata.create_all(bind=_TEST_ENGINE)

from analysis.push_trigger import (
    FIRE_PERCENTILE,
    MIN_REARM_BAND_PP,
    REARM_NOISE_MULTIPLE,
    PushThresholds,
    evaluate_push,
    resolve_push_thresholds,
)
from analysis import analyze_report as ar
from alerts.telegram_analyze import build_analyze_message, build_push_message

NOW = datetime(2026, 9, 21, 12, 0, 0)
FAIR = 240_000_000


def _thresholds(fire=4.11, rearm=3.36):
    return PushThresholds(fire_at=fire, rearm_at=rearm, band_pp=fire - rearm,
                          noise_pp=0.46, sample_size=200, status="OK")


def _seed(readings):
    """(timestamp, mode, discount_size_pp) -> snapshots with four platform prices."""
    session = _test_get_session()
    session.query(PlatformPrice).delete()
    session.query(MarketSnapshot).delete()
    for timestamp, mode, size in readings:
        # price chosen so the mean of the three cheapest gives exactly `size`
        basis = FAIR * (1 - size / 100.0)
        snapshot = MarketSnapshot(
            timestamp=timestamp, world_gold_usd=4300.0, usd_irr=230_000.0,
            fair_price=FAIR, premium_percent=-size, collection_mode=mode,
        )
        session.add(snapshot)
        session.flush()
        for index, name in enumerate(("A", "B", "C", "D")):
            price = basis if index < 3 else basis * 1.05
            session.add(PlatformPrice(snapshot_id=snapshot.id, platform_name=name,
                                      timestamp=timestamp, price_irr=price))
    session.commit()
    session.close()


def _hourly(sizes, start=None, mode="scheduled"):
    """Hourly readings ending just before today, so the settled window sees them and
    the current-gap lookup still finds a recent one."""
    base = start or (NOW - timedelta(hours=len(sizes) + 14))
    return [(base + timedelta(hours=i), mode, v) for i, v in enumerate(sizes)]


class KPISPC6(unittest.TestCase):

    # -- 1. the gate, exhaustively --------------------------------------------

    def test_01_armed_and_above_the_level_fires(self):
        d = evaluate_push(-4.50, _thresholds(), armed=True)
        self.assertTrue(d.should_fire)
        self.assertFalse(d.armed_after)
        self.assertEqual(d.reason, "FIRED")

    def test_02_armed_and_below_the_level_does_not_fire(self):
        d = evaluate_push(-3.90, _thresholds(), armed=True)
        self.assertFalse(d.should_fire)
        self.assertTrue(d.armed_after)
        self.assertEqual(d.reason, "BELOW_FIRE")

    def test_03_disarmed_and_still_above_stays_quiet(self):
        # The whole point of the band: one episode, one message.
        d = evaluate_push(-4.90, _thresholds(), armed=False)
        self.assertFalse(d.should_fire)
        self.assertFalse(d.armed_after)
        self.assertEqual(d.reason, "HELD_BY_BAND")

    def test_04_disarmed_inside_the_band_stays_disarmed(self):
        # Between re-arm and fire: the discount has eased but not enough to call the
        # episode over.
        d = evaluate_push(-3.80, _thresholds(), armed=False)
        self.assertFalse(d.should_fire)
        self.assertFalse(d.armed_after)

    def test_05_disarmed_and_below_the_rearm_level_rearms(self):
        d = evaluate_push(-3.00, _thresholds(), armed=False)
        self.assertFalse(d.should_fire)
        self.assertTrue(d.armed_after)
        self.assertEqual(d.reason, "REARMED")

    def test_06_unknown_state_fails_OPEN(self):
        """The single most important assertion in this file.

        armed=None means state.json could not be read. Treating that as disarmed
        would reinstate exactly the latch that suppressed 100 BUY candidates: one
        lost cache and the push goes silent permanently, with nothing to notice.
        """
        d = evaluate_push(-4.50, _thresholds(), armed=None)
        self.assertTrue(d.should_fire, "unknown armed state must not suppress")
        self.assertEqual(d.reason, "FIRED_STATE_UNKNOWN")

    def test_07_unknown_state_below_the_level_still_does_not_fire(self):
        d = evaluate_push(-3.00, _thresholds(), armed=None)
        self.assertFalse(d.should_fire)
        self.assertTrue(d.armed_after)

    def test_08_no_thresholds_abstains_and_leaves_the_gate_armed(self):
        d = evaluate_push(-9.99, PushThresholds(), armed=None)
        self.assertFalse(d.should_fire)
        self.assertTrue(d.armed_after)
        self.assertEqual(d.reason, "NO_DATA")

    def test_09_no_reading_abstains(self):
        d = evaluate_push(None, _thresholds(), armed=True)
        self.assertFalse(d.should_fire)
        self.assertEqual(d.reason, "NO_DATA")

    def test_10_the_8_9_august_flicker_produces_one_message_not_four(self):
        """Replay of real readings. A bare threshold sent four alerts across 41
        hours for a single episode, two of them 35 minutes apart."""
        readings = [4.30, 4.16, 4.03, 3.59, 3.77, 3.90, 4.42, 4.05,
                    4.15, 4.16, 4.07, 4.03, 4.06, 4.10, 4.11, 4.05, 3.87, 3.88]
        th = _thresholds()
        armed, fired, naive, prev_above = True, 0, 0, False
        for size in readings:
            d = evaluate_push(-size, th, armed)
            if d.should_fire:
                fired += 1
            armed = d.armed_after
            above = size >= th.fire_at
            if above and not prev_above:
                naive += 1
            prev_above = above
        self.assertEqual(naive, 4, "the replay must reproduce the original flicker")
        self.assertEqual(fired, 1, "the band must collapse it to a single message")

    # -- 2. thresholds --------------------------------------------------------

    def test_11_rearm_is_a_width_below_fire_not_a_second_percentile(self):
        # A percentile pair's width drifted 0.24 to 0.84 pp across the observation
        # period while the noise it filters was 0.46 pp, so at the narrow end it
        # would have been half the noise. The band is tied to the noise directly.
        _seed(_hourly([2.0 + (i % 40) * 0.1 for i in range(200)]))
        t = resolve_push_thresholds(_test_get_session(), now=NOW)
        self.assertEqual(t.status, "OK")
        self.assertAlmostEqual(t.fire_at - t.rearm_at, t.band_pp, places=3)
        self.assertGreaterEqual(t.band_pp, MIN_REARM_BAND_PP)

    def test_12_a_quiet_market_cannot_collapse_the_band(self):
        # Noise-proportional alone would shrink to nothing if the market went flat,
        # reinstating the flicker at the worst moment.
        _seed(_hourly([3.0] * 60))
        t = resolve_push_thresholds(_test_get_session(), now=NOW)
        if t.status == "OK":
            self.assertGreaterEqual(t.band_pp, MIN_REARM_BAND_PP)

    def test_13_thresholds_abstain_below_the_minimum_sample(self):
        _seed(_hourly([3.0, 3.5, 4.0]))
        t = resolve_push_thresholds(_test_get_session(), now=NOW)
        self.assertEqual(t.status, "INSUFFICIENT_DATA")
        self.assertIsNone(t.fire_at)

    def test_14_the_level_is_a_rank_not_a_constant(self):
        # A fixed level went stale four times in this codebase. p85 of the discount
        # moved 0.81 pp across six weeks of real data.
        self.assertEqual(FIRE_PERCENTILE, 85)
        self.assertEqual(REARM_NOISE_MULTIPLE, 1.5)

    def test_15_a_broken_session_degrades_rather_than_raising(self):
        class _Broken:
            def query(self, *a, **k):
                raise RuntimeError("connection lost")
        self.assertEqual(resolve_push_thresholds(_Broken()).status, "INSUFFICIENT_DATA")

    # -- 3. the report --------------------------------------------------------

    def test_16_the_reference_excludes_today_and_the_readers_own_clicks(self):
        session = _test_get_session()
        rows = _hourly([3.0] * 50, start=NOW - timedelta(days=5))
        rows += [(NOW - timedelta(hours=2), "scheduled", 9.9)]      # today
        rows += [(NOW - timedelta(days=2), "user", 9.9)]            # a click
        _seed(rows)
        series = ar._settled_series(_test_get_session(), NOW, 30)
        self.assertTrue(all(abs(item[2]) < 9.0 for item in series),
                        "today's readings or user rows leaked into the reference")

    def test_17_an_episode_cannot_span_an_unobserved_stretch(self):
        """Collection runs 06:00 to 21:00 local, so the series carries a nine-hour
        nightly gap. Bridging it reported a two-hour zone as fifteen hours."""
        base = NOW - timedelta(days=8)
        rows = _hourly([2.0] * 30, start=base)
        # Eight deep readings of thirty-eight, so the 85th percentile lands above the
        # quiet baseline rather than inside it. Two spells of four, 19 hours apart --
        # a stretch nobody observed.
        deep = [(base + timedelta(hours=40 + i), "scheduled", 9.0) for i in range(4)]
        deep += [(base + timedelta(hours=63 + i), "scheduled", 9.0) for i in range(4)]
        _seed(rows + deep)
        zone = ar.resolve_deep_zone(_test_get_session(), current_gap=-2.0, now=NOW)
        self.assertEqual(zone.status, "OK")
        self.assertLess(zone.longest_hours, ar.MAX_EPISODE_GAP_HOURS + 1,
                        "an episode bridged a gap nobody observed")

    def test_18_level_outcomes_never_look_backwards(self):
        source = inspect.getsource(ar.resolve_level_outcomes)
        self.assertIn("series[index + 1:]", source,
                      "outcomes must be drawn strictly forward of the reading")

    def test_19_typical_is_the_median_under_a_word_a_reader_knows(self):
        _seed(_hourly([1.0, 2.0, 3.0, 4.0, 5.0] * 12))
        d = ar.resolve_distribution(_test_get_session(), current_gap=-2.0, now=NOW)
        self.assertEqual(d.status, "OK")
        self.assertAlmostEqual(d.typical, 3.0, places=1)
        self.assertAlmostEqual(d.low, 1.0, places=1)
        self.assertAlmostEqual(d.high, 5.0, places=1)

    def test_20_the_report_writes_nothing(self):
        # skills/telegram-product.md: a user request must not silently become an
        # Analysis Wing execution or historical learning observation.
        _seed(_hourly([2.0 + (i % 30) * 0.1 for i in range(120)]))
        session = _test_get_session()
        before = (session.query(MarketSnapshot).count(),
                  session.query(PlatformPrice).count())
        ar.build_analyze_report(_test_get_session(), now=NOW)
        after = (session.query(MarketSnapshot).count(),
                 session.query(PlatformPrice).count())
        session.close()
        self.assertEqual(before, after)

    def test_21_the_report_module_issues_no_writes(self):
        source = inspect.getsource(ar)
        for forbidden in (".add(", ".commit(", ".delete(", "save_"):
            self.assertNotIn(forbidden, source,
                             f"{forbidden} in a read-only report module")

    # -- 4. neither surface may recommend -------------------------------------

    def _report(self):
        _seed(_hourly([2.0 + (i % 30) * 0.1 for i in range(150)]))
        return ar.build_analyze_report(_test_get_session(), now=NOW)

    def test_22_analyze_carries_no_decision(self):
        text = build_analyze_message(self._report())
        for word in ("BUY", "SELL", "WAIT", "Candidate", "recommend"):
            self.assertNotIn(word, text)

    def test_23_analyze_says_it_is_not_a_forecast(self):
        text = build_analyze_message(self._report())
        self.assertIn("not a forecast", text)
        self.assertNotIn("Forecast for", text)

    def test_24_the_push_carries_no_decision(self):
        d = evaluate_push(-4.50, _thresholds(), armed=True)
        text = build_push_message(d, None, lowest=234_100_000, low_name="Milli",
                                  basis_count=3, platform_count=11)
        for word in ("BUY", "SELL", "WAIT", "recommend", "should"):
            self.assertNotIn(word, text)

    def test_25_the_decision_record_is_hidden_until_it_has_a_sample(self):
        # Three decisions is an anecdote. market-analyst.md forbids manufacturing
        # confidence from a small sample.
        text = build_analyze_message(self._report())
        self.assertNotIn("Decision record", text)
        self.assertNotIn("Decisions since", text)

    def test_26_the_vocabulary_matches_UPDATE(self):
        # A synonym reads as a new concept to someone who did not write it. These
        # four were each introduced and then removed during SP-C.
        text = build_analyze_message(self._report())
        d = evaluate_push(-4.50, _thresholds(), armed=True)
        text += build_push_message(d, None)
        for banned in ("widening", "widened", "grew", "deepening", "dearer"):
            self.assertNotIn(banned, text.lower())

    def test_27_counts_read_as_english(self):
        from alerts.telegram_analyze import _times
        self.assertEqual(_times(1), "1 time")
        self.assertEqual(_times(0), "0 times")
        self.assertEqual(_times(25), "25 times")

    # -- 5. wiring ------------------------------------------------------------

    def test_28_report_mode_returns_before_any_collection(self):
        import main
        source = inspect.getsource(main.main)
        report_index = source.find("if report_only:")
        collect_index = source.find("get_market_prices()")
        self.assertGreater(report_index, 0)
        self.assertGreater(collect_index, report_index,
                           "the report wing must return before prices are collected")

    def test_29_the_armed_flag_is_persisted_after_the_push(self):
        # save_state runs before the analysis snapshot is built, so without an
        # explicit save the flag set by the push is discarded, the gate reads unknown
        # every run, fails open every run, and fires on every reading above the level.
        import main
        source = inspect.getsource(main.main)
        push_index = source.find("_evaluate_deep_discount_push")
        self.assertGreater(push_index, 0)
        self.assertIn("save_state(state)", source[push_index:],
                      "the armed flag is never saved after the push sets it")

    def test_30_the_workflow_declares_the_report_wing(self):
        path = os.path.join(os.path.dirname(__file__), "..", ".github",
                            "workflows", "gold-monitor.yml")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("- report", text)
        self.assertIn("REPORT_ONLY", text)
        # REPORT_ONLY must be independent of SCHEDULED_RUN, or a report would run
        # the Analysis Wing.
        self.assertNotIn("REPORT_ONLY: ${{ github.event_name == 'schedule'", text)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPISPC6)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 55)
    print(f"SP-C.12 KPI RESULT: {passed}/{result.testsRun} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
