"""KPI -- signal confirmation, and the BUY message (hotfix on main, 2026-09-29).

On 2026-09-29 at 14:01 Tehran the engine issued its first live BUY since SP-C.15, and
it was wrong. It rested on one platform: Taline's collector read a copy of Taline's web
page that its CDN had been serving to GitHub's non-Iranian runners for a day, 2.4 pp
below every other platform. Valuation and momentum both read the single cheapest price,
so one stale quote carried two of the three legs, and nothing between the candidate and
the alert asked whether anything was odd (SP_C_HANDOFF.md sections 37 and 38).

The fix, approved by the product owner, leaves the SP-A matrix alone and adds a
confirmation check between the candidate and the final decision:

- a BUY needs the second-cheapest platform to be heavily discounted on its own record,
  judged by the same classifier and the same settled, non-user window the valuation
  leg uses;
- any signal needs the dollar rate to be today's (SP_C_HANDOFF.md 34.3);
- any signal needs world gold to be a live quote.

Load-bearing properties, each asserted below:

- **It fails closed.** A check that cannot run holds the signal. The push fails open
  because its failure mode is silence about a measurement; a BUY is a recommendation.
- **The candidate survives.** CANDIDATE != FINAL: a held BUY is still recorded as the
  candidate, and the stored reason says why it was held.
- **The 09-29 case is held**, replayed from the production prices of that minute.
- **The message says "heavily discounted", never "cheap"**, and prints no internal
  label, by product decision on 2026-09-29.
- **A stale Taline quote never enters a calculation.** Validation discards a Taline
  price more than 1.0% from the other platforms' median, on either side, and only
  Taline's: its source is the proven problem, and a genuinely cheap platform elsewhere
  is information.
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

from analysis.bubble_position import RelativeValuation
from analysis.confirmation import SignalConfirmation, resolve_signal_confirmation
from caluclator.signal_state import build_signal_state
from alerts.telegram_signal import build_buy_signal_message

FAIR = 250_000_000
THRESHOLDS = {"buy_premium_percent": -1.5, "sell_premium_percent": 3.0, "cooldown_hours": 24}
# 14:01 Tehran on 2026-09-29, the minute of the stale BUY.
NOW = datetime(2026, 9, 29, 10, 31)
# Local midnight of that day, which is where the settled window ends.
REFERENCE_END = datetime(2026, 9, 28, 20, 30)

# The eleven prices of 2026-09-29 14:01, as gaps to fair value in percent.
STALE_BUY_GAPS = {
    "Taline": -4.93, "Milli": -2.53, "Invi": -1.78, "MioGold": -1.64, "Daric": -1.46,
    "Ayyareh": -1.41, "WallGold": -1.37, "Eligold": -1.36, "HoorGold": -1.27,
    "Parasteh": -1.19, "Goldika": -0.36,
}


def _local(day_offset, hour, minute=1):
    """Naive UTC for a Tehran wall-clock time relative to 2026-09-29."""
    local = datetime(2026, 9, 29, hour, minute) + timedelta(days=day_offset)
    return local - timedelta(hours=3, minutes=30)


def _markets(gaps):
    return {name: {"price": FAIR * (1 + gap / 100.0), "status": "OK"}
            for name, gap in gaps.items()}


def _clear():
    session = _test_get_session()
    session.query(PlatformPrice).delete()
    session.query(MarketSnapshot).delete()
    session.commit()
    session.close()


def _add(timestamp, mode, second_gap, usd=244_000):
    """One snapshot whose second-cheapest platform sits at `second_gap`."""
    session = _test_get_session()
    snapshot = MarketSnapshot(
        timestamp=timestamp, world_gold_usd=4150.0, usd_irr=usd, fair_price=FAIR,
        premium_percent=second_gap - 0.3, collection_mode=mode,
    )
    session.add(snapshot)
    session.flush()
    for i, offset in enumerate((-0.3, 0.0, 0.2, 0.4, 0.8)):
        session.add(PlatformPrice(snapshot_id=snapshot.id, platform_name=f"P{i}",
                                  price_irr=FAIR * (1 + (second_gap + offset) / 100.0),
                                  timestamp=timestamp))
    session.commit()
    session.close()


def _seed_window():
    """160 settled scheduled readings, second-cheapest spread evenly over -4.0..-1.0.

    Plus two populations that must NOT be ranked against: 60 user readings and 30
    readings from the current, unsettled day, all at -10%. Either one alone moves a
    -3.0% reading out of the cheap band if it leaks into the pool: 54 of 160 settled
    readings sit at or below -3.0% (rank 34), against (54+60)/220 = 52 with the user
    rows and (54+30)/190 = 44 with the unsettled day.
    """
    _clear()
    count = 160
    for k in range(count):
        gap = -4.0 + 3.0 * k / (count - 1)
        _add(REFERENCE_END - timedelta(days=20) + timedelta(hours=3 * k), "scheduled", gap)
    for k in range(60):
        _add(REFERENCE_END - timedelta(days=10) + timedelta(minutes=37 * k), "user", -10.0)
    for k in range(30):
        _add(REFERENCE_END + timedelta(hours=10) + timedelta(minutes=3 * k), "scheduled", -10.0)


def _seed_dollar(with_update=False):
    """The dollar input as it moved on 2026-09-28 evening and 09-29 morning."""
    _clear()
    _add(_local(-1, 21, 0), "scheduled", -2.0, usd=244_500)
    for hour in (6, 7, 8, 9, 10):
        _add(_local(0, hour), "scheduled", -2.0, usd=244_800)
    if with_update:
        _add(_local(0, 11), "scheduled", -2.0, usd=250_100)


def _resolve(markets, usd=244_800, now=NOW, world_from_fallback=False):
    session = _test_get_session()
    try:
        return resolve_signal_confirmation(session, markets, FAIR, usd,
                                           world_from_fallback, THRESHOLDS, now=now)
    finally:
        session.close()


def _passing():
    return SignalConfirmation(second_platform="Milli", second_gap=-4.5, second_percentile=3,
                              second_confirms=True, dollar_live=True,
                              dollar_updated_at=_local(0, 11), world_live=True, status="OK")


def _buy_state(confirmation):
    """A reading the matrix turns into a BUY candidate: CHEAP, IMPROVING, all below fair."""
    markets = _markets({f"P{i}": -4.0 - 0.1 * i for i in range(11)})
    return build_signal_state(
        premium=-4.0, fair_price=FAIR, lowest_price=FAIR * 0.95, markets=markets,
        previous_premium=-3.5, thresholds=THRESHOLDS, last_alert=None,
        valuation="CHEAP", confirmation=confirmation,
    )


def _sell_state(confirmation):
    """EXPENSIVE, WEAKENING, all above fair: a SELL candidate."""
    markets = _markets({f"P{i}": 4.0 + 0.1 * i for i in range(11)})
    return build_signal_state(
        premium=4.0, fair_price=FAIR, lowest_price=FAIR * 1.04, markets=markets,
        previous_premium=3.5, thresholds=THRESHOLDS, last_alert=None,
        valuation="EXPENSIVE", confirmation=confirmation,
    )


class KPISignalConfirmation(unittest.TestCase):

    # -- 1. the gate ------------------------------------------------------------

    def test_01_a_confirmed_buy_becomes_final(self):
        state = _buy_state(_passing())
        self.assertEqual(state.candidate_decision, "BUY")
        self.assertEqual(state.final_decision, "BUY")
        self.assertEqual(state.held_reason, "")

    def test_02_an_unconfirmed_buy_is_held_and_the_candidate_survives(self):
        failing = _passing()
        failing.second_confirms = False
        state = _buy_state(failing)
        self.assertEqual(state.candidate_decision, "BUY", "CANDIDATE != FINAL")
        self.assertEqual(state.final_decision, "WAIT")
        self.assertIn("only one platform shows this discount", state.held_reason)
        self.assertIn("BUY held:", state.reason, "the stored reason must say why")
        self.assertNotIn("hysteresis", state.reason,
                         "a held BUY must not be explained as a hysteresis hold")

    def test_03_a_check_that_could_not_run_holds_the_signal(self):
        state = _buy_state(SignalConfirmation())
        self.assertEqual(state.final_decision, "WAIT", "the gate must fail closed")
        self.assertIn("could not be checked", state.held_reason)

    def test_04_no_confirmation_supplied_means_no_gate(self):
        """The calculator's contract for callers that predate the gate. The production
        caller always supplies one -- kpi_coherence.test_29 asserts that."""
        self.assertEqual(_buy_state(None).final_decision, "BUY")

    def test_05_sell_skips_the_second_platform_but_not_the_inputs(self):
        passing = _passing()
        passing.second_confirms = None
        self.assertEqual(_sell_state(passing).final_decision, "SELL",
                         "SELL rests on the cheapest price, already the conservative one")
        stale = _passing()
        stale.dollar_live = False
        state = _sell_state(stale)
        self.assertEqual(state.final_decision, "WAIT")
        self.assertIn("dollar rate has not updated today", state.held_reason)

    def test_06_a_cached_world_gold_price_holds_the_signal(self):
        cached = _passing()
        cached.world_live = False
        self.assertIn("world gold is a cached price", _buy_state(cached).held_reason)

    # -- 2. the second platform -------------------------------------------------

    def test_07_the_stale_taline_buy_of_2026_09_29_is_held(self):
        _seed_window()
        result = _resolve(_markets(STALE_BUY_GAPS))
        self.assertEqual(result.second_platform, "Milli")
        self.assertAlmostEqual(result.second_gap, -2.53, places=6)
        self.assertFalse(result.second_confirms,
                         "Milli at -2.53% ranks mid-window: nothing confirms Taline")
        self.assertIn("Milli", result.held_reason("BUY"))

    def test_08_a_broad_discount_is_confirmed(self):
        _seed_window()
        gaps = {"A": -4.8, "B": -4.5, "C": -4.2, "D": -3.9, "E": -3.5}
        result = _resolve(_markets(gaps))
        self.assertEqual(result.second_platform, "B")
        self.assertTrue(result.second_confirms)

    def test_09_user_rows_and_the_unsettled_day_are_not_ranked_against(self):
        """-3.0% sits at rank 34 of the settled scheduled window. With the 60 user
        rows or the current day's rows in the pool it would rank above 40."""
        _seed_window()
        result = _resolve(_markets({"A": -3.3, "B": -3.0, "C": -2.0}))
        self.assertLess(result.second_percentile, 40)
        self.assertTrue(result.second_confirms)

    def test_10_the_direction_gate_applies_to_the_second_platform_too(self):
        """A rank alone cannot call a platform heavily discounted when it sits above
        -1.5% -- the same direction gate as the valuation leg (SP-C.15)."""
        _clear()
        for k in range(60):
            _add(REFERENCE_END - timedelta(days=5) + timedelta(hours=2 * k), "scheduled",
                 -1.0 + 0.9 * k / 59)
        result = _resolve(_markets({"A": -1.4, "B": -1.2, "C": -0.5}))
        self.assertLess(result.second_percentile, 40)
        self.assertFalse(result.second_confirms)

    def test_11_too_little_history_cannot_confirm(self):
        _clear()
        for k in range(10):
            _add(REFERENCE_END - timedelta(days=1) + timedelta(hours=k), "scheduled", -2.0)
        result = _resolve(_markets({"A": -5.0, "B": -4.9}))
        self.assertIsNone(result.second_confirms)
        self.assertIn("could not be checked", result.held_reason("BUY"))

    # -- 3. the dollar ------------------------------------------------------------

    def test_12_before_the_open_the_dollar_is_yesterdays(self):
        _seed_dollar()
        self.assertFalse(_resolve({}, usd=244_800, now=_local(0, 9, 31)).dollar_live)

    def test_13_after_the_open_the_rate_must_have_moved(self):
        _seed_dollar()
        self.assertFalse(_resolve({}, usd=244_800, now=_local(0, 11, 31)).dollar_live)
        moved = _resolve({}, usd=250_100, now=_local(0, 11, 31))
        self.assertTrue(moved.dollar_live)
        self.assertEqual(moved.dollar_updated_at, _local(0, 11, 31),
                         "a rate first seen now took effect now")

    def test_14_the_update_time_is_when_the_rate_took_effect(self):
        _seed_dollar(with_update=True)
        result = _resolve({}, usd=250_100, now=_local(0, 12, 31))
        self.assertTrue(result.dollar_live)
        self.assertEqual(result.dollar_updated_at, _local(0, 11))

    def test_15_from_13_00_an_unmoved_rate_is_the_days_rate(self):
        _seed_dollar()
        self.assertTrue(_resolve({}, usd=244_800, now=_local(0, 13, 31)).dollar_live)

    def test_16_a_missing_dollar_cannot_be_checked(self):
        _seed_dollar()
        result = _resolve({}, usd=None, now=_local(0, 14))
        self.assertIsNone(result.dollar_live)
        self.assertIn("could not be checked", result.held_reason("SELL"))

    # -- 4. failing closed in production -----------------------------------------

    def test_17_the_production_wrapper_fails_closed(self):
        import main
        original = main.get_session
        try:
            main.get_session = lambda: None
            result = main._resolve_signal_confirmation({}, FAIR, 244_800, False, THRESHOLDS)
            self.assertEqual(result.status, "NO_SESSION")
            self.assertIsNotNone(result.held_reason("BUY"))

            class _Session:
                def query(self, *args, **kwargs):
                    raise RuntimeError("query failed")

                def close(self):
                    pass

            main.get_session = lambda: _Session()
            result = main._resolve_signal_confirmation(_markets(STALE_BUY_GAPS), FAIR,
                                                       244_800, False, THRESHOLDS)
            self.assertEqual(result.status, "ERROR")
            self.assertIsNotNone(result.held_reason("BUY"))
        finally:
            main.get_session = original

    # -- 5. the BUY message -------------------------------------------------------

    def _message(self, premium=-4.93, gap=-4.12):
        state = _buy_state(_passing())
        state.premium = premium
        valuation = RelativeValuation(
            gap=gap, percentile=9, bigger_than=91, deep_at=3.5, move_label="a large move",
            move_percentile=70, basis_price=FAIR * (1 + gap / 100.0), basis_count=3,
            window_days=30, sample_size=207, coverage_days=14, sampling="SCHEDULED",
            status="OK",
        )
        markets = _markets({"Milli": -4.4, "Invi": -4.1, "MioGold": -3.9, "Daric": -3.0,
                            "Ayyareh": -2.8, "WallGold": -2.7, "Eligold": -2.6,
                            "HoorGold": -2.5, "Parasteh": -2.4, "Goldika": -1.8,
                            "Taline": -2.2})
        return build_buy_signal_message(
            fair=FAIR, markets=markets, signal_state=state, confirmation=_passing(),
            valuation=valuation, baselines=None, now=NOW, cooldown_hours=24,
        )

    def test_18_the_message_says_heavily_discounted_not_cheap(self):
        text = self._message()
        self.assertIn("Heavily discounted for its own record", text)
        for label in ("CHEAP", "Cheap for", "IMPROVING", "DISCOUNT_WIDENING",
                      "DISCOUNT WIDENING", "SUPPORTIVE", "DISCOUNT_DOMINANT"):
            self.assertNotIn(label, text, f"internal label {label!r} reached the reader")

    def test_19_the_message_carries_updates_number_not_the_single_cheapest(self):
        """One word, one number: the Discount line uses the three-cheapest basis UPDATE
        prints, not the stored single-cheapest premium the old alert printed."""
        text = self._message(premium=-4.93, gap=-3.08)
        self.assertIn("3.08%  below fair value", text)
        self.assertNotIn("4.93", text)
        self.assertIn("from the 3 cheapest of 11", text)
        self.assertIn("91% of the last 30 days", text)
        self.assertIn("If 3.50% or more", text)

    def test_20_the_message_shows_its_checks_and_does_not_instruct(self):
        text = self._message()
        self.assertEqual(text.count("GOLDPremium:"), 1, "exactly one application header")
        self.assertIn("BUY SIGNAL", text)
        self.assertIn("confirms (Milli)", text)
        self.assertIn("live (updated 11:01)", text)
        self.assertIn("Decision support, not an instruction to trade.", text)
        self.assertIn("No repeat BUY signal before 14:01 tomorrow.", text)

    # -- 6. the Taline collector --------------------------------------------------

    def test_21_taline_asks_its_cdn_for_a_fresh_page(self):
        import collector.taline as taline

        calls = []
        page = ('<span class="elementor-heading-title">قیمت ۱گرم طلای ۱۸‌عیار:</span>'
                '<span class="elementor-heading-title">24,994,000</span>')

        class _Response:
            text = page

            def raise_for_status(self):
                pass

        def fake_get(url, **kwargs):
            calls.append(kwargs)
            return _Response()

        original = taline.requests.get
        taline.requests.get = fake_get
        try:
            result = taline.get_taline_price()
        finally:
            taline.requests.get = original
        self.assertEqual(result["price"], 249_940_000.0)
        headers = calls[0]["headers"]
        self.assertEqual(headers.get("Cache-Control"), "no-cache")
        self.assertEqual(headers.get("Pragma"), "no-cache")
        self.assertIsInstance(calls[0]["params"]["_"], int)

    def test_22_the_gate_sits_between_the_candidate_and_hysteresis(self):
        source = inspect.getsource(build_signal_state)
        gate = source.index("held_reason(candidate)")
        hysteresis = source.index("apply_hysteresis(")
        self.assertLess(gate, hysteresis, "a held candidate must never reach hysteresis")

    # -- 7. a stale Taline never enters a calculation ------------------------------

    def _validate(self, gaps):
        from validation.data import validate_market_prices
        prices = {name: {"price": FAIR * (1 + gap / 100.0), "status": "OK"}
                  for name, gap in gaps.items()}
        return validate_market_prices(prices)

    def test_23_the_stale_taline_of_2026_09_29_is_discarded(self):
        valid = self._validate(STALE_BUY_GAPS)
        self.assertNotIn("Taline", valid, "3.6% below the others is a stale copy")
        self.assertEqual(len(valid), 10, "no other platform may be discarded with it")

    def test_24_a_taline_in_line_with_the_market_is_kept(self):
        gaps = dict(STALE_BUY_GAPS, Taline=-1.55)   # 0.2% below the others' median
        self.assertIn("Taline", self._validate(gaps))

    def test_25_a_stale_copy_above_the_market_is_discarded_too(self):
        """In a falling market a stale copy sits above the others."""
        gaps = dict(STALE_BUY_GAPS, Taline=+0.2)
        self.assertNotIn("Taline", self._validate(gaps))

    def test_26_too_few_others_to_judge_keeps_the_quote(self):
        self.assertIn("Taline", self._validate({"Taline": -4.0, "Milli": -1.0, "Invi": -1.0}))

    def test_27_only_the_stale_prone_platform_is_checked(self):
        """The check is about Taline's source, not about outliers. A genuinely cheap
        platform elsewhere is information, and the confirmation check -- not the
        validator -- decides what a single cheap platform may trigger."""
        gaps = dict(STALE_BUY_GAPS, Taline=-1.4, Milli=-4.5)
        valid = self._validate(gaps)
        self.assertIn("Milli", valid)
        self.assertIn("Taline", valid)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(KPISignalConfirmation)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print()
    print("=" * 55)
    print(f"SIGNAL CONFIRMATION KPI RESULT: {passed}/{total} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
