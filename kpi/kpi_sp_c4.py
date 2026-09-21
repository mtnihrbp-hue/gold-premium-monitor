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

from analysis.bubble_position import resolve_change_magnitude, resolve_relative_valuation
from alerts.telegram_update_v1 import (
    _build_market,
    _build_the_number,
    _build_verdict,
    _cheapest_platforms,
    _gap_delta,
    _gap_movement,
    _gap_naming,
    _outside_basis_prices,
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


class _Valuation:
    """Stands in for RelativeValuation with values chosen per test."""

    def __init__(self, gap=-5.68, bigger_than=6, deep_at=4.0574, basis_price=228_233_333,
                 basis_count=3, move_label="a large move", status="OK", window_days=30):
        self.gap = gap
        self.percentile = None if bigger_than is None else 100 - bigger_than
        self.bigger_than = bigger_than
        self.deep_at = deep_at
        self.basis_price = basis_price
        self.basis_count = basis_count
        self.move_label = move_label
        self.move_percentile = 60
        self.window_days = window_days
        self.sample_size = 232
        self.coverage_days = 31
        self.sampling = "MIXED"
        self.status = status


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


_UNSET = object()


def _render_number(premium=-5.68, position=None, magnitude=None, baselines=None,
                   markets=None, signal=None, valuation=_UNSET):
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
        valuation=_Valuation() if valuation is _UNSET else valuation,
    )


def _seed(premiums, start=None):
    """Seed market snapshots one hour apart, oldest first."""
    session = _test_get_session()
    session.query(PlatformPrice).delete()
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


def _reset_snapshots():
    session = _test_get_session()
    session.query(PlatformPrice).delete()
    session.query(MarketSnapshot).delete()
    session.commit()
    session.close()


def _seed_priced(session, timestamp, mode, price):
    """A snapshot with four platform prices, so the trimmed basis is resolvable."""
    snapshot = MarketSnapshot(
        timestamp=timestamp, world_gold_usd=4285.0, usd_irr=230_700.0,
        fair_price=FAIR, premium_percent=-3.0, collection_mode=mode,
    )
    session.add(snapshot)
    session.flush()
    for offset, name in enumerate(("A", "B", "C", "D")):
        session.add(PlatformPrice(
            snapshot_id=snapshot.id, platform_name=name, timestamp=timestamp,
            price_irr=price + offset * 100_000,
        ))


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

    def test_19_the_basis_is_named_on_the_line_stating_the_number(self):
        # The figure rests on a trimmed set of platforms, so the line stating it says
        # which. Naming the source lower down left the reader connecting a number to
        # its origin across four lines and a blank, and it was reported as missing
        # from a message that contained it.
        text = _render_number()
        lines = text.split("\n")
        index = next(i for i, line in enumerate(lines) if "below fair value" in line)
        self.assertIn("from the 3 cheapest of 4", lines[index + 1])

    def test_20_block_shows_where_the_platforms_outside_the_basis_sit(self):
        # Without this a single platform's move is indistinguishable from a market
        # move, which is exactly what produced a false "unusually large" reading.
        text = _render_number()
        self.assertIn("Cheapest 3", text)
        # Prices are stored in Rials and shown in millions of Tomans.
        self.assertIn("The other 1 platforms: 23.39M - 23.39M.", text)

    def test_21_outside_basis_prices_exclude_the_basis_and_any_failure(self):
        others = _outside_basis_prices(MARKETS, ["MioGold", "Milli"])
        self.assertEqual(others, [231_100_000, 233_900_000])

    def test_21b_cheapest_platforms_are_returned_cheapest_first(self):
        self.assertEqual(
            _cheapest_platforms(MARKETS, 3),
            [("MioGold", 224_800_000), ("Milli", 230_200_000), ("Taline", 231_100_000)],
        )

    def test_22_references_are_named_once_in_the_readers_own_clock(self):
        # Stored timestamps are UTC, produced by the scheduled runner and the
        # database. Every reader is in Iran, UTC+3:30. Printing the stored value
        # told a reader the day began at 02:31 when their own clock said 06:01,
        # which invites them to check a figure against the wrong reference.
        #
        # The footnote sits in MARKET and serves both sections; THE NUMBER used to
        # carry a second copy naming the same two references.
        table = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                              233_900_000, 9_100_000, -5.68, _baselines(),
                              markets=MARKETS, valuation=_Valuation())
        self.assertIn("Run = 17:01 (last scheduled), Today = 06:01 (first today).", table)
        self.assertNotIn("All changes are vs", _render_number())

    def test_22b_local_conversion_is_a_fixed_iran_offset(self):
        from alerts.helpers import format_clock
        from timeutil import to_tehran
        self.assertEqual(format_clock(datetime(2026, 9, 15, 2, 31)), "06:01")
        self.assertEqual(format_clock(datetime(2026, 9, 15, 21, 0)), "00:30")  # next day
        self.assertIsNone(format_clock(None))
        self.assertIsNone(to_tehran(None))

    def test_23_threshold_is_stated_as_a_rule_without_promising_a_reward(self):
        text = _render_number()
        self.assertIn("If 4.06% or more  (30D)", text)
        # A rank inside the window, not a level measured against outcomes. The
        # decision scorecard measured an edge of 0.0, so the message must not present
        # it as a buy trigger.
        for claim in ("Buy Opportunity", "reward", "profit"):
            self.assertNotIn(claim, text)

    def test_23c_the_deep_level_is_the_one_the_push_acts_on(self):
        """One label, one number. Until 2026-09-21 UPDATE printed the 40th percentile
        of the signed gap under the words "Deep discount" while ANALYZE and the push
        used the 85th of the size -- 3.29% against 3.70% on the same day, in two
        messages a reader sees together. A reader at 3.40% was told deep and got no
        push."""
        import inspect
        from analysis import bubble_position as bp
        from analysis.analyze_report import DEEP_ZONE_PERCENTILE
        from analysis.push_trigger import FIRE_PERCENTILE
        self.assertEqual(DEEP_ZONE_PERCENTILE, bp.DEEP_DISCOUNT_PERCENTILE)
        self.assertEqual(FIRE_PERCENTILE, bp.DEEP_DISCOUNT_PERCENTILE)
        # Not merely equal by coincidence: the value must be resolved in one place.
        source = inspect.getsource(bp.resolve_relative_valuation)
        self.assertIn("deep_discount_threshold(reference_readings(", source,
                      "UPDATE must read the shared level, not compute its own")

    def test_23d_the_level_is_a_positive_size_and_survives_the_ranking_gate(self):
        """The threshold is drawn from the settled non-user pool, which the scheduled
        gate does not narrow. Measured on 2026-09-21 the two pools put p85 at 3.70%
        and 3.64%, so a threshold that followed the ranking pool would have split into
        two numbers again the day the gate opened."""
        from analysis.bubble_position import (
            deep_discount_threshold, reference_readings,
        )
        from datetime import datetime as _dt
        end = _dt(2026, 9, 15)
        series = ([(end - timedelta(hours=i + 1), "scheduled", -2.0) for i in range(40)]
                  + [(end - timedelta(hours=i + 1), "user", -9.0) for i in range(40)]
                  + [(end + timedelta(hours=1), "scheduled", -9.0)])
        pool = reference_readings(series, end)
        self.assertTrue(all(mode != "user" for _, mode, _ in pool))
        self.assertTrue(all(ts < end for ts, _, _ in pool))
        level = deep_discount_threshold(pool)
        self.assertGreater(level, 0, "the level is a size, never signed")
        self.assertAlmostEqual(level, 2.0, places=6)
        self.assertIsNone(deep_discount_threshold(pool[:5]), "must abstain on a thin pool")

    def test_23e_the_level_never_excludes_the_reading_that_produced_it(self):
        """Gaps are computed from prices and land on values like 8.999999999999996.
        Rounding the level to 9.0 lifted it above its own source reading, and a zone
        with eight readings in it measured zero episodes."""
        from analysis.bubble_position import deep_discount_threshold
        from datetime import datetime as _dt
        base = _dt(2026, 9, 1)
        quiet = [(base + timedelta(hours=i), "scheduled", -2.0000000000000018)
                 for i in range(30)]
        deep = [(base + timedelta(hours=40 + i), "scheduled", -8.999999999999996)
                for i in range(8)]
        level = deep_discount_threshold(quiet + deep)
        qualifying = [g for _, _, g in deep if abs(g) >= level]
        self.assertEqual(len(qualifying), 8,
                         "the level excluded the readings it was drawn from")

    def test_23b_rank_line_names_the_discount_not_an_undefined_cheapness(self):
        # "Cheaper than 29%" left the reader asking cheaper than what. The subject is
        # the discount, and the table footnote already defines a bigger discount as
        # the cheaper one, so one word carries both.
        text = _render_number()
        self.assertIn("Bigger than", text)
        self.assertIn("6% of the last 30 days", text)
        self.assertNotIn("Cheaper than", text)

    def test_24_premium_mode_claims_nothing_about_a_deep_discount(self):
        """The level is a size drawn from a record that holds no premiums. Printing
        "Deep discount" beside a reading above fair value is a claim about the other
        side of the market, which has no design yet -- the sell-side mirror is
        deliberately absent, not implied."""
        text = _render_number(valuation=_Valuation(gap=2.40, deep_at=1.20, bigger_than=40))
        self.assertIn("2.40%  above fair value", text)
        self.assertNotIn("Deep discount", text)
        self.assertNotIn("Cheap zone", text)
        # The rank still applies: it describes where the reading sits either way.
        self.assertIn("Bigger than", text)

    def test_25_unchanged_movement_carries_no_size_label(self):
        from analysis.bubble_position import cheap_basis_price, signed_gap
        # The run baseline holds the current reading's own prices, so nothing moved.
        baselines = _baselines()
        baselines.run.platform_prices = {
            name: info["price"] for name, info in MARKETS.items()
            if info["price"] is not None
        }
        baselines.run.fair_price = FAIR
        gap = signed_gap(cheap_basis_price(baselines.run.platform_prices.values()), FAIR)
        text = _render_number(baselines=baselines,
                              valuation=_Valuation(gap=gap, move_label="a normal move"))
        self.assertIn("unchanged", text)
        self.assertNotIn("a normal move", text)

    def test_26_rank_lines_are_omitted_when_history_is_too_short(self):
        text = _render_number(valuation=_Valuation(status="INSUFFICIENT_DATA"))
        self.assertNotIn("Bigger than", text)
        self.assertNotIn("Deep discount", text)

    def test_26b_valuation_falls_back_to_the_stored_premium_when_absent(self):
        # A failed valuation query must degrade the message, never prevent it.
        text = _render_number(premium=-3.61, valuation=None)
        self.assertIn("3.61%  below fair value", text)
        self.assertNotIn("Bigger than", text)

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
                             markets=MARKETS, valuation=_Valuation())
        self.assertIn("Discount", text)
        self.assertNotIn("Bubble", text)

    def test_29b_table_and_block_rest_on_the_same_basis(self):
        # The table carried the all-platform average beside a trimmed headline, so
        # the two halves described different prices under one heading.
        text = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                             233_900_000, 9_100_000, -5.68, _baselines(),
                             markets=MARKETS, valuation=_Valuation())
        self.assertIn("Cheap 3", text)
        self.assertNotIn("Platform ", text)

    def test_29c_table_column_matches_the_row_label_in_the_block(self):
        # "Day" in the table and "vs Today" in the block named one reference twice.
        text = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                             233_900_000, 9_100_000, -5.68, _baselines(),
                             markets=MARKETS, valuation=_Valuation())
        self.assertIn("Today", text)
        self.assertIn("vs Today", _render_number())

    def test_30_market_footnote_flips_with_the_sign(self):
        discount = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                                 233_900_000, 9_100_000, -5.68, _baselines(),
                                 markets=MARKETS, valuation=_Valuation())
        premium = _build_market(4285.0, 230_700.0, FAIR, PLATFORM_AVG, LOWEST,
                                233_900_000, 9_100_000, 2.40, _baselines(),
                                markets=MARKETS, valuation=_Valuation(gap=2.40))
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

    def test_33_update_carries_no_buy_wait_sell_verdict(self):
        # Removed by product decision. UPDATE is a view of the market; the chain
        # that produces a decision (valuation, momentum, structure, conflict) is
        # not in this message, so a bare verdict asked to be trusted rather than
        # understood. It belongs in ANALYZE alongside its reasoning.
        from alerts.telegram_update_v1 import _build_verdict
        text = _build_verdict(_Signal(4, 0), _Position(6, -4.0574))
        for verdict in ("WAIT", "BUY", "SELL", "Candidate"):
            self.assertNotIn(verdict, text)

    def test_34_header_carries_no_band_sentence(self):
        # "Below its own recent average" restated what "Bigger than 29% of the last
        # 30 days" says one line later, in vaguer terms and without the figure.
        text = _build_verdict(_Signal(4, 0), _Position(6, -4.0574))
        self.assertEqual(text, "<b>GOLDPremium: UPDATE</b>")

    # -- the trimmed basis ----------------------------------------------------

    def test_35_valuation_basis_is_the_mean_of_the_three_cheapest(self):
        from analysis.bubble_position import cheap_basis_price, signed_gap
        self.assertAlmostEqual(
            cheap_basis_price([224_800_000, 230_200_000, 231_100_000, 233_900_000]),
            228_700_000, places=0,
        )
        # Fewer platforms than the basis width still returns a value.
        self.assertAlmostEqual(cheap_basis_price([100.0, 200.0]), 150.0)
        self.assertIsNone(cheap_basis_price([]))
        self.assertAlmostEqual(signed_gap(90.0, 100.0), -10.0)
        self.assertIsNone(signed_gap(90.0, 0))

    # -- the reference distribution is settled, and excludes the reader ------

    def _seed_days(self, days=8, per_day=6, user_on_day=None):
        """Priced snapshots across several local days, oldest first."""
        from timeutil import local_date, to_utc
        _reset_snapshots()
        session = _test_get_session()
        start = to_utc(datetime.combine(local_date(NOW), datetime.min.time()))
        for day_back in range(days, 0, -1):
            day_start = start - timedelta(days=day_back)
            for slot in range(per_day):
                mode = "scheduled"
                if user_on_day is not None and day_back == user_on_day and slot == 0:
                    mode = "user"
                # Priced near FAIR so the resulting gaps land in a realistic
                # -4% to -6% band rather than outside any plausible reading.
                _seed_priced(session, day_start + timedelta(hours=6 + slot),
                             mode, 225_000_000 + day_back * 400_000 + slot * 30_000)
        # today's own readings, which must not enter the reference pool
        for slot in range(4):
            _seed_priced(session, start + timedelta(hours=slot), "scheduled",
                         210_000_000 + slot * 10_000)
        session.commit()
        session.close()

    def test_35b_threshold_is_constant_across_one_local_day(self):
        # It moved fifteen times in three days: the percentile index is
        # int(0.40 * n), so it advanced every two or three readings as the window
        # grew under it. Anchored to completed days it steps only at the boundary.
        self._seed_days()
        session = _test_get_session()
        morning = resolve_relative_valuation(session, markets=MARKETS, fair_price=FAIR,
                                             now=NOW.replace(hour=4))
        evening = resolve_relative_valuation(session, markets=MARKETS, fair_price=FAIR,
                                             now=NOW.replace(hour=19))
        self.assertEqual(morning.status, "OK")
        self.assertEqual(morning.deep_at, evening.deep_at)

    def test_35c_threshold_steps_at_the_day_boundary(self):
        self._seed_days()
        session = _test_get_session()
        today = resolve_relative_valuation(session, markets=MARKETS, fair_price=FAIR,
                                           now=NOW)
        yesterday = resolve_relative_valuation(session, markets=MARKETS, fair_price=FAIR,
                                               now=NOW - timedelta(days=1))
        self.assertNotEqual(today.deep_at, yesterday.deep_at)

    def test_35d_todays_readings_stay_out_of_the_reference(self):
        # Ranking today against a pool containing today is what let the pool move
        # under the reading being ranked.
        self._seed_days()
        session = _test_get_session()
        result = resolve_relative_valuation(session, markets=MARKETS, fair_price=FAIR,
                                            now=NOW)
        # 8 days x 6 readings seeded before today; today's 4 must be excluded.
        self.assertEqual(result.sample_size, 48)

    def test_35e_the_readers_own_clicks_are_excluded(self):
        # Pressing Update moved the threshold being read: one click on 2026-09-19
        # shifted it 0.0106 pp. PROJECT_MEMORY.md already required that user calls
        # not serve as a baseline; the fallback sample had not been honouring it.
        self._seed_days(user_on_day=3)
        session = _test_get_session()
        result = resolve_relative_valuation(session, markets=MARKETS, fair_price=FAIR,
                                            now=NOW)
        self.assertEqual(result.sampling, "MIXED")
        self.assertEqual(result.sample_size, 47)   # one of the 48 was user-triggered

    def test_35f_the_live_rank_still_moves_within_a_day(self):
        # Only the reference is frozen. "Bigger than X%" ranks the current reading
        # and must react to it, or the message would stop responding to the market.
        self._seed_days()
        session = _test_get_session()
        cheap = dict(MARKETS, MioGold={"status": "OK", "price": 200_000_000})
        dear = dict(MARKETS, MioGold={"status": "OK", "price": 237_000_000})
        a = resolve_relative_valuation(session, markets=cheap, fair_price=FAIR, now=NOW)
        b = resolve_relative_valuation(session, markets=dear, fair_price=FAIR, now=NOW)
        self.assertEqual(a.deep_at, b.deep_at)
        self.assertNotEqual(a.bigger_than, b.bigger_than)

    def test_36_window_and_reading_are_built_on_the_same_basis(self):
        # Comparing a trimmed reading against a minimum-based window would report a
        # change of definition as a change in the market. This is the failure the
        # basis change exists to prevent, so it is asserted rather than assumed.
        import analysis.bubble_position as bp
        source = inspect.getsource(bp._basis_series)
        body = source.split('"""')[-1]          # skip the docstring, which names both
        self.assertIn("cheap_basis_price", body)
        self.assertNotIn("premium_percent", body)

    def test_37_scheduled_sample_needs_both_a_count_and_a_calendar_span(self):
        # 30 readings at 16 a day is under two days, and a line reading "of the last
        # 30 days" would be measuring against Tuesday. The Iranian weekend also runs
        # 0.28 and 0.40 pp deeper than the weekday median, so a seven-day span either
        # contains a weekend or does not.
        from analysis.bubble_position import (
            MIN_SCHEDULED_READINGS, MIN_SCHEDULED_COVERAGE_DAYS)
        self.assertEqual(MIN_SCHEDULED_READINGS, 30)
        self.assertEqual(MIN_SCHEDULED_COVERAGE_DAYS, 14)

    def test_38_mixed_sampling_is_used_until_the_span_is_met(self):
        # Three days of scheduled readings must not trigger the clean path just
        # because the count clears 30.
        _reset_snapshots()
        session = _test_get_session()
        base = NOW - timedelta(days=3)
        for i in range(40):
            _seed_priced(session, base + timedelta(hours=i), "scheduled", 23_000_000 + i)
        for i in range(40):
            _seed_priced(session, NOW - timedelta(days=20 + i // 2), "unknown", 22_500_000 + i)
        session.commit()
        session.close()
        result = resolve_relative_valuation(
            _test_get_session(), markets=MARKETS, fair_price=FAIR, now=NOW)
        self.assertEqual(result.sampling, "MIXED")

    def test_39_query_failure_degrades_rather_than_raising(self):
        class _Broken:
            def query(self, *a, **k):
                raise RuntimeError("connection lost")
        result = resolve_relative_valuation(_Broken(), markets=MARKETS, fair_price=FAIR)
        self.assertEqual(result.status, "INSUFFICIENT_DATA")
        self.assertIsNone(result.bigger_than)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPISPC4)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 55)
    print(f"SP-C.4 KPI RESULT: {passed}/{result.testsRun} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
