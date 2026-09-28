"""KPI — SP-C.2: Decision scorecard.

Verifies that recorded decisions are scored against the bubble rather than the
price, and that a hit rate is always reported next to naive baselines.

The central property asserted here is that a system which always returns the same
decision must show zero edge. Scoring price movement instead would have credited
such a system with roughly 58% on this project's history, because the local price
rises on its own.
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
import database.repository as _repo_module
_repo_module.get_session = _test_get_session

from database.models import Base, MarketSnapshot, MarketState
Base.metadata.create_all(bind=_TEST_ENGINE)

from analysis.decision_scorecard import (
    score_decisions,
    INCONCLUSIVE_DEADBAND_PP,
    MIN_SCORED_DECISIONS,
)

NOW = datetime(2026, 9, 14, 12, 0, 0)


def _reset():
    session = _test_get_session()
    session.query(MarketState).delete()
    session.query(MarketSnapshot).delete()
    session.commit()
    session.close()


def _market_state(snapshot_id, decision, timestamp):
    """MarketState with every non-nullable column populated.

    Only the decision is meaningful to the scorecard; the rest satisfy the schema.
    """
    return MarketState(
        snapshot_id=snapshot_id,
        valuation_state="CHEAP",
        momentum_state="NEUTRAL",
        premium_direction="DISCOUNT_STABLE",
        structure_state="DISCOUNT_DOMINANT",
        conflict_state="NEUTRAL",
        candidate_decision=decision,
        final_decision=decision,
        timestamp=timestamp,
    )


def _seed_pairs(pairs, decision, gap_hours=24, spacing_days=2):
    """Seed (bubble_now, bubble_later) pairs, each with a decision attached.

    Each pair is placed far enough from the next that one pair's later reading
    cannot serve as another pair's outcome.
    """
    session = _test_get_session()
    base = NOW - timedelta(days=spacing_days * len(pairs) + 5)
    for index, (start_bubble, later_bubble) in enumerate(pairs):
        first_time = base + timedelta(days=spacing_days * index)
        snapshot = MarketSnapshot(
            timestamp=first_time, fair_price=100.0, premium_percent=start_bubble,
            world_gold_usd=4000.0, usd_irr=200000.0,
        )
        session.add(snapshot)
        session.flush()
        session.add(_market_state(snapshot.id, decision, first_time))
        session.add(MarketSnapshot(
            timestamp=first_time + timedelta(hours=gap_hours),
            fair_price=100.0, premium_percent=later_bubble,
            world_gold_usd=4000.0, usd_irr=200000.0,
        ))
    session.commit()
    session.close()


class KPISPC2(unittest.TestCase):

    def setUp(self):
        _reset()

    # --- guards -----------------------------------------------------------

    def test_01_missing_session_does_not_raise(self):
        card = score_decisions(None)
        self.assertEqual(card.status, "INSUFFICIENT_DATA")

    def test_02_no_data_is_insufficient(self):
        card = score_decisions(_test_get_session())
        self.assertEqual(card.status, "INSUFFICIENT_DATA")
        self.assertIsNone(card.hit_rate)

    def test_03_decision_without_outcome_is_unresolved(self):
        session = _test_get_session()
        snapshot = MarketSnapshot(
            timestamp=NOW, fair_price=100.0, premium_percent=-4.0,
            world_gold_usd=4000.0, usd_irr=200000.0,
        )
        session.add(snapshot)
        session.flush()
        session.add(_market_state(snapshot.id, "WAIT", NOW))
        session.commit()
        session.close()
        card = score_decisions(_test_get_session())
        self.assertEqual(card.unresolved, 1)
        self.assertEqual(card.scored, 0)

    # --- scoring direction ------------------------------------------------

    def test_04_buy_correct_when_discount_shrinks(self):
        _seed_pairs([(-5.0, -4.0)] * 25, "BUY")
        card = score_decisions(_test_get_session())
        self.assertEqual(card.incorrect, 0)
        self.assertGreater(card.correct, 0)

    def test_05_buy_incorrect_when_discount_grows(self):
        _seed_pairs([(-4.0, -5.0)] * 25, "BUY")
        card = score_decisions(_test_get_session())
        self.assertEqual(card.correct, 0)
        self.assertGreater(card.incorrect, 0)

    def test_06_wait_correct_when_discount_grows(self):
        _seed_pairs([(-4.0, -5.0)] * 25, "WAIT")
        card = score_decisions(_test_get_session())
        self.assertEqual(card.incorrect, 0)
        self.assertGreater(card.correct, 0)

    def test_07_wait_incorrect_when_discount_shrinks(self):
        _seed_pairs([(-5.0, -4.0)] * 25, "WAIT")
        self.assertEqual(score_decisions(_test_get_session()).correct, 0)

    def test_08_sell_scored_like_hold_off(self):
        _seed_pairs([(-4.0, -5.0)] * 25, "SELL")
        card = score_decisions(_test_get_session())
        self.assertGreater(card.correct, 0)
        self.assertEqual(card.incorrect, 0)

    def test_09_small_move_is_inconclusive(self):
        tiny = INCONCLUSIVE_DEADBAND_PP / 2
        _seed_pairs([(-4.0, -4.0 + tiny)] * 25, "BUY")
        card = score_decisions(_test_get_session())
        self.assertEqual(card.correct, 0)
        self.assertEqual(card.incorrect, 0)
        self.assertGreater(card.inconclusive, 0)

    # --- baselines --------------------------------------------------------

    def test_10_single_decision_system_has_zero_edge(self):
        # Mixed outcomes, but the system always says the same thing.
        pairs = [(-4.0, -5.0)] * 13 + [(-5.0, -4.0)] * 12
        _seed_pairs(pairs, "WAIT")
        card = score_decisions(_test_get_session())
        self.assertEqual(card.edge_vs_baseline, 0.0)

    def test_11_baselines_are_complementary(self):
        pairs = [(-4.0, -5.0)] * 13 + [(-5.0, -4.0)] * 12
        _seed_pairs(pairs, "WAIT")
        card = score_decisions(_test_get_session())
        self.assertAlmostEqual(
            card.always_buy_rate + card.always_wait_rate, 100.0, places=1
        )

    def test_12_edge_is_hit_rate_minus_best_baseline(self):
        pairs = [(-4.0, -5.0)] * 13 + [(-5.0, -4.0)] * 12
        _seed_pairs(pairs, "WAIT")
        card = score_decisions(_test_get_session())
        self.assertAlmostEqual(
            card.edge_vs_baseline,
            round(card.hit_rate - card.best_baseline_rate, 1),
            places=1,
        )

    def test_13_perfect_system_beats_the_baseline(self):
        session = _test_get_session()
        base = NOW - timedelta(days=120)
        for index in range(30):
            shrinking = index % 2 == 0
            start_bubble = -4.5
            later = -4.0 if shrinking else -5.0
            decision = "BUY" if shrinking else "WAIT"
            first_time = base + timedelta(days=2 * index)
            snapshot = MarketSnapshot(
                timestamp=first_time, fair_price=100.0, premium_percent=start_bubble,
                world_gold_usd=4000.0, usd_irr=200000.0,
            )
            session.add(snapshot)
            session.flush()
            session.add(_market_state(snapshot.id, decision, first_time))
            session.add(MarketSnapshot(
                timestamp=first_time + timedelta(hours=24),
                fair_price=100.0, premium_percent=later,
                world_gold_usd=4000.0, usd_irr=200000.0,
            ))
        session.commit()
        session.close()
        card = score_decisions(_test_get_session())
        self.assertEqual(card.hit_rate, 100.0)
        self.assertGreater(card.edge_vs_baseline, 0)

    # --- reporting --------------------------------------------------------

    def test_14_confidence_insufficient_below_minimum(self):
        _seed_pairs([(-5.0, -4.0)] * (MIN_SCORED_DECISIONS - 5), "BUY")
        self.assertEqual(
            score_decisions(_test_get_session()).confidence, "INSUFFICIENT_DATA"
        )

    def test_15_confidence_low_above_minimum(self):
        _seed_pairs([(-5.0, -4.0)] * (MIN_SCORED_DECISIONS + 5), "BUY")
        self.assertEqual(score_decisions(_test_get_session()).confidence, "LOW")

    def test_16_counts_sum_to_scored(self):
        pairs = [(-4.0, -5.0)] * 13 + [(-5.0, -4.0)] * 12
        _seed_pairs(pairs, "WAIT")
        card = score_decisions(_test_get_session())
        self.assertEqual(
            card.scored, card.correct + card.incorrect + card.inconclusive
        )

    def test_17_breakdown_reported_per_decision(self):
        _seed_pairs([(-5.0, -4.0)] * 25, "BUY")
        card = score_decisions(_test_get_session())
        self.assertIn("BUY", card.by_decision)
        self.assertEqual(card.by_decision["BUY"]["correct"], card.correct)

    def test_18_horizon_beyond_history_resolves_nothing(self):
        _seed_pairs([(-5.0, -4.0)] * 25, "BUY")
        card = score_decisions(_test_get_session(), horizon_hours=24 * 365)
        self.assertEqual(card.scored, 0)
        self.assertGreater(card.unresolved, 0)

    def test_19_scoring_uses_bubble_not_price(self):
        # Price identical everywhere, only the bubble moves. A price-based rule
        # could not score these at all; a bubble-based one scores every case.
        _seed_pairs([(-5.0, -4.0)] * 25, "BUY")
        card = score_decisions(_test_get_session())
        self.assertGreater(card.scored, 0)
        self.assertEqual(card.hit_rate, 100.0)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPISPC2)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 55)
    print(f"SP-C.2 KPI RESULT: {passed}/{result.testsRun} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
