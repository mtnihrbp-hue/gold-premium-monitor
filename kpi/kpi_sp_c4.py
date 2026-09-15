"""KPI — SP-C.4: UPDATE speaks one language, in the direction the market is in.

The message previously described the same gap in two vocabularies. THE NUMBER
reported a signed premium, PRICE & BUBBLE DYNAMICS reported a direction toward
MORE/LESS DISCOUNT, and the MARKET table carried a signed delta whose sign was the
opposite of the one a reader would infer from the block above it. The same market
movement therefore appeared three times with three different presentations, and the
two halves of the message could be read as contradicting each other.

The message now states the gap as a positive size with its side named once, states
movement as an increase or decrease of that size, and attaches what the move means
for a buyer so nothing has to be inferred from a sign.

Three properties are load-bearing and are what these tests guard:

- Consequence is derived from the signed premium, never from the size of the gap.
  Size alone is wrong across the zero line, where a move from a 0.5% discount to a
  0.5% premium leaves the size unchanged while the market has moved a full point.
- Every line that names discount or premium flips with the sign. The market has been
  in discount for all 319 recorded readings, so the premium branch has never once
  executed in production and cannot be checked by observation.
- The gap is measured at the cheapest platform. A single platform moving alone
  changes the headline while the market has not moved, which happened in production
  on 2026-09-15 when MioGold fell 2.87% against a flat field and moved the reported
  discount 2.07 pp. The reader is therefore told which platform sets the number and
  where the others sit.
"""

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

from database.models import Base, MarketSnapshot
Base.metadata.create_all(bind=_TEST_ENGINE)

from analysis.bubble_position import resolve_change_magnitude
from alerts.telegram_update_v1 import (
    _build_market,
    _build_the_number,
    _gap_delta,
    _gap_movement,
    _gap_naming,
    _other_platform_prices,
)
from update.baseline_resolver import BaselineSnapshot, UpdateBaselines
from analysis.trend_resolver import SevenDayTrend

NOW = datetime(2026, 9, 15, 14, 31, 0)


class _Signal:
    def __init__(self, below, above):
        self.platforms_below_fair = below
        self.platforms_above_fair = above
        self.final_decision = "WAIT"
        self.candidate_decision = "WAIT"
        self.momentum = "NEUTRAL"


class _Position:
    def __init__(self, percentile, cheap_below, window_days=30):
        self.percentile = percentile
        self.cheap_below = cheap_below
        self.window_days = window_days
        self.confidence = "LOW"


def _baseline(timestamp, premium, fair, platform_avg):
    return BaselineSnapshot(
        timestamp=timestamp,
        xau_usd=4285.0,
        usd_irr=230_700.0,
        fair_price=fair,
        premium_percent=premium,
        platform_prices={},
        platform_average=platform_avg,
        platform_count=11,
    )


def _baselines(run_premium=-3.61, day_premium=-3.80, run_fair=238_000_000,
               run_avg=231_500_000):
    return UpdateBaselines(
        run=_baseline(datetime(2026, 9, 15, 13, 31), run_premium, run_fair, run_avg),
        day=_baseline(datetime(2026, 9, 15, 2, 31), day_premium, run_fair, run_avg),
        seven_day=SevenDayTrend(
            xau_usd=4300.0, usd_irr=232_000.0, fair_price=240_000_000,
            platform_average=232_000_000, premium_percent=-3.4, day_count=7,
        ),
        rep_gold_acceleration=None,
        rep_gold_acceleration_label="N/A",
        bubble_movement="STABLE",
        bubble_magnitude_change=None,
        price_direction="FALLING",
        price_direction_raw=-0.14,
        bubble_movement_deadband=0.05,
        acceleration_threshold=0.0001,
        day_source="scheduled",
    )


MARKETS = {
    "MioGold": {"status": "OK", "price": 224_800_000},
    "Milli": {"status": "OK", "price": 230_200_000},
    "Goldika": {"status": "OK", "price": 233_900_000},
    "Taline": {"status": "OK", "price": 231_100_000},
    "Broken": {"status": "FAILED", "price": None},
}

FAIR = 238_400_000
LOWEST = 224_800_000
PLATFORM_AVG = 231_200_000


def _render_number(premium=-5.68, position=None, magnitude=None, baselines=None,
                   markets=None, signal=None):
    return _build_the_number(
        premium=premium,
        lowest=LOWEST,
        fair=FAIR,
        platform_avg=PLATFORM_AVG,
        markets=MARKETS if markets is None else markets,
        signal_state=_Signal(4, 0) if signal is None else signal,
        position=_Position(6, -4.0574) if position is None else position,
        magnitude=magnitude,
        baselines=_baselines() if baselines is None else baselines,
    )


def _seed(premiums, start=None):
    """Seed market snapshots one hour apart, oldest first."""
    session = _test_get_session()
    session.query(MarketSnapshot).delete()
    base = start or (NOW - timedelta(hours=len(premiums)))
    for index, premium in enumerate(premiums):
        session.add(MarketSnapshot(
            timestamp=base + timedelta(hours=index),
            world_gold_usd=4285.0,
            usd_irr=230_700.0,
            fair_price=FAIR,
            premium_percent=premium,
        ))
    session.commit()
    session.close()


class KPISPC4(unittest.TestCase):

    # -- naming flips with the sign -------------------------------------------

    def test_01_negative_premium_is_named_discount_below_fair(self):
        self.assertEqual(_gap_naming(-3.61), ("Discount", "below"))

    def test_02_positive_premium_is_named_premium_above_fair(self):
        self.assertEqual(_gap_naming(2.40), ("Premium", "above"))

    def test_03_missing_premium_degrades_rather_than_guessing_a_side(self):
        self.assertEqual(_gap_naming(None), ("Gap", "from"))

    # -- the delta is a size, in percentage points ----------------------------

    def test_04_gap_delta_is_the_change_in_size_not_in_signed_premium(self):
        # -3.61 to -5.68 is a discount growing by 2.07 points. The signed delta is
        # -2.07, which printed in the table as a negative next to a discount the
        # message describes as larger.
        self.assertAlmostEqual(_gap_delta(-5.68, -3.61), 2.07, places=4)

    def test_05_gap_delta_is_none_when_either_side_is_missing(self):
        self.assertIsNone(_gap_delta(-5.68, None))
        self.assertIsNone(_gap_delta(None, -3.61))

    # -- movement, and what it means for a buyer ------------------------------

    def test_06_growing_discount_is_reported_as_increased_and_cheaper(self):
        self.assertEqual(_gap_movement(-5.68, -3.61), "increased 2.07 pp — cheaper")

    def test_07_shrinking_discount_is_reported_as_decreased_and_expensive(self):
        self.assertEqual(_gap_movement(-3.61, -5.68), "decreased 2.07 pp — more expensive")

    def test_08_growing_premium_is_more_expensive_not_cheaper(self):
        # The consequence has to invert with the sign. Reusing the discount wording
        # here would tell a reader that a rising premium is a better entry.
        self.assertEqual(_gap_movement(3.00, 2.00), "increased 1.00 pp — more expensive")

    def test_09_shrinking_premium_is_cheaper(self):
        self.assertEqual(_gap_movement(2.00, 3.00), "decreased 1.00 pp — cheaper")

    def test_10_crossing_fair_value_is_named_rather_than_sized(self):
        # Sizes are equal on both sides, so an increase/decrease reading would
        # report "unchanged" on a full point of movement.
        self.assertEqual(_gap_movement(0.50, -0.50), "crossed fair value — more expensive")
        self.assertEqual(_gap_movement(-0.50, 0.50), "crossed fair value — cheaper")

    def test_11_movement_below_display_precision_reads_unchanged(self):
        # 0.004 rounds to 0.00 at the two decimals the message shows, and the text
        # must not assert a change the reader cannot see in the number.
        self.assertEqual(_gap_movement(-3.614, -3.610), "unchanged")

    def test_12_consequence_can_be_suppressed_for_the_second_reference(self):
        self.assertEqual(
            _gap_movement(-5.68, -3.61, with_consequence=False),
            "increased 2.07 pp",
        )

    def test_13_movement_is_none_when_no_baseline_exists(self):
        self.assertIsNone(_gap_movement(-5.68, None))

    # -- move size is a rank, not a distance from a centre --------------------

    def test_14_magnitude_ranks_against_past_absolute_changes(self):
        _seed([-3.0 + 0.1 * i for i in range(40)])  # forty moves of 0.10 pp
        result = resolve_change_magnitude(_test_get_session(), change_pp=2.0, now=NOW)
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.percentile, 100)
        self.assertEqual(result.label, "unusually large")

    def test_15_a_move_smaller_than_most_is_a_normal_move(self):
        _seed([-3.0 + 0.1 * i for i in range(40)])
        result = resolve_change_magnitude(_test_get_session(), change_pp=0.01, now=NOW)
        self.assertEqual(result.label, "a normal move")

    def test_16_magnitude_ignores_direction_and_ranks_size_only(self):
        _seed([-3.0 + 0.1 * i for i in range(40)])
        up = resolve_change_magnitude(_test_get_session(), change_pp=2.0, now=NOW)
        down = resolve_change_magnitude(_test_get_session(), change_pp=-2.0, now=NOW)
        self.assertEqual(up.label, down.label)
        self.assertEqual(up.percentile, down.percentile)

    def test_17_magnitude_abstains_below_the_minimum_sample(self):
        _seed([-3.0, -3.1, -3.2])
        result = resolve_change_magnitude(_test_get_session(), change_pp=2.0, now=NOW)
        self.assertEqual(result.status, "INSUFFICIENT_DATA")
        self.assertEqual(result.label, "UNKNOWN")

    # -- the rendered block ---------------------------------------------------

    def test_18_block_states_the_gap_as_a_positive_size_with_its_side(self):
        text = _render_number()
        self.assertIn("5.68%  below fair value", text)
        self.assertNotIn("-5.68", text)

    def test_19_platform_is_named_on_the_line_stating_the_number(self):
        # Naming it lower down, beside the market low, left the reader connecting a
        # figure to its source across four lines and a blank. It was reported as
        # missing from a message that contained it.
        text = _render_number()
        headline = text.split("\n")
        index = next(i for i, line in enumerate(headline) if "below fair value" in line)
        self.assertIn("at MioGold, the cheapest of 4", headline[index + 1])

    def test_20_block_shows_where_the_other_platforms_sit(self):
        # Without this a single platform's move is indistinguishable from a market
        # move, which is exactly what produced a false "unusually large" reading.
        text = _render_number()
        # Prices are stored in Rials and shown in millions of Tomans.
        self.assertIn("The other 3 platforms: 23.02M - 23.39M.", text)

    def test_21_other_platform_prices_exclude_the_low_and_any_failure(self):
        others = _other_platform_prices(MARKETS, "MioGold")
        self.assertEqual(others, [230_200_000, 231_100_000, 233_900_000])

    def test_22_block_names_both_references_by_time(self):
        text = _render_number()
        self.assertIn("All changes are vs the 13:31 reading,", text)
        self.assertIn("except vs Today, which is vs 02:31.", text)

    def test_23_threshold_is_stated_as_a_rule_without_promising_a_reward(self):
        text = _render_number()
        self.assertIn("If 4.06% or more  (30D)", text)
        # The threshold is the 40th percentile of the window, not a level measured
        # against outcomes. The decision scorecard measured an edge of 0.0, so the
        # message must not present it as a buy trigger.
        for claim in ("Buy Opportunity", "reward", "profit"):
            self.assertNotIn(claim, text)

    def test_24_premium_mode_states_the_cheap_rule_as_an_upper_bound(self):
        text = _render_number(premium=2.40, position=_Position(60, 1.20))
        self.assertIn("2.40%  above fair value", text)
        self.assertIn("Cheap zone", text)
        self.assertIn("If 1.20% or less  (30D)", text)
        self.assertNotIn("Deep discount", text)

    def test_25_unchanged_movement_carries_no_size_label(self):
        magnitude = resolve_change_magnitude(None, change_pp=0.0)
        magnitude.status = "OK"
        magnitude.label = "a normal move"
        text = _render_number(premium=-3.61, baselines=_baselines(run_premium=-3.61),
                              magnitude=magnitude)
        self.assertIn("unchanged", text)
        self.assertNotIn("a normal move", text)

    def test_26_position_lines_are_omitted_when_history_is_too_short(self):
        text = _render_number(position=_Position(None, None))
        self.assertNotIn("Cheaper than", text)
        self.assertNotIn("Deep discount", text)

    def test_27_confidence_is_not_surfaced_to_the_reader(self):
        # Deliberately withheld: the reader is shown the sample the number rests on
        # through the window itself, and a bare "LOW" was noise they could not act on.
        self.assertNotIn("Confidence", _render_number())

    def test_28_platform_consensus_reports_the_measure_not_agreement(self):
        # "all 11 agree" implied price consensus and was false on a day one platform
        # sat 2.87% off the field. The count is about position against fair value.
        self.assertIn("all 4 below fair value", _render_number())
        self.assertIn("2 of 4 below fair value", _render_number(signal=_Signal(2, 2)))

    # -- the table speaks the same language ------------------------------------

    def test_29_market_table_row_is_the_gap_size_not_the_signed_premium(self):
        text = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                             233_900_000, 9_100_000, -5.68, _baselines(),
                             markets=MARKETS)
        self.assertIn("Discount", text)
        self.assertNotIn("Bubble", text)
        self.assertIn("+2.07", text)   # size grew; the signed delta was -2.07

    def test_30_market_footnote_flips_with_the_sign(self):
        discount = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                                 233_900_000, 9_100_000, -5.68, _baselines(),
                                 markets=MARKETS)
        premium = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                                233_900_000, 9_100_000, 2.40, _baselines(),
                                markets=MARKETS)
        self.assertIn("A bigger discount is cheaper.", discount)
        self.assertIn("A bigger premium is more expensive.", premium)
        self.assertNotIn("A bigger discount is cheaper.", premium)

    def test_31_the_word_bubble_is_gone_from_the_reader_facing_surface(self):
        # One vocabulary. "Bubble" was an internal term that appeared next to
        # "discount" describing the same quantity.
        self.assertNotIn("Bubble", _render_number())

    def test_32_dynamics_section_is_not_rebuilt_by_accident(self):
        import alerts.telegram_update_v1 as module
        self.assertFalse(hasattr(module, "_build_dynamics"))
        self.assertFalse(hasattr(module, "_bubble_direction"))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPISPC4)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 55)
    print(f"SP-C.4 KPI RESULT: {passed}/{result.testsRun} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
