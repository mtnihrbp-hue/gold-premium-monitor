"""KPI — SP-C.3: Outcome evaluation is reachable from the runtime.

C.5 already proves the evaluation mechanism works: kpi_pre_sp_c5.py covers backfill,
idempotency, tolerance, look-ahead protection and COMPLETE handling. None of that was
the problem.

The problem was that the runtime only ever evaluated the snapshot it had just created,
whose +1h, +6h and +24h targets are all still in the future, so every evaluation
recorded INSUFFICIENT_DATA and nothing returned once the horizons matured. After
hourly collection began, all 213 production evaluations were still unresolved.

These tests therefore assert reachability rather than arithmetic. This is the fifth
occurrence in this project of capability that was built, tested and never invoked —
the C14C news collector, the Analyze trigger, the unenforced analysis window, the RUN
baseline, and outcome evaluation — so the wiring itself is what needs a guard.
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
import database.repository as _repo_module
_repo_module.get_session = _test_get_session

from database.models import Base, AnalysisSnapshot, PriceObservation, OutcomeEvaluation
Base.metadata.create_all(bind=_TEST_ENGINE)

import analysis.snapshot_builder as snapshot_builder
from analysis.outcome_evaluator import backfill_outcome_evaluations

NOW = datetime(2026, 9, 15, 12, 0, 0)


def _reset():
    session = _test_get_session()
    session.query(OutcomeEvaluation).delete()
    session.query(PriceObservation).delete()
    session.query(AnalysisSnapshot).delete()
    session.commit()
    session.close()


def _seed_snapshot(timestamp, premium=-4.0):
    session = _test_get_session()
    snap = AnalysisSnapshot(
        snapshot_type="analysis",
        analysis_timestamp=timestamp,
        source_run_id=f"analysis_{timestamp.strftime('%Y%m%d_%H%M%S')}",
        premium_percent=premium,
        rep_gold_price=230_000_000,
        xau_usd=4300.0,
        usd_irr=233_000,
    )
    session.add(snap)
    session.commit()
    snapshot_id = snap.id
    session.close()
    return snapshot_id


def _seed_observation(timestamp, price, instrument="REP_IRAN_GOLD", source="milli"):
    session = _test_get_session()
    session.add(PriceObservation(
        instrument=instrument, source=source, timestamp=timestamp,
        price=price, freshness="FRESH", quote_side="SINGLE",
    ))
    session.commit()
    session.close()


class KPISPC3(unittest.TestCase):

    def setUp(self):
        _reset()

    # --- reachability -----------------------------------------------------

    def test_01_snapshot_builder_invokes_the_backfill(self):
        """The regression that mattered: the runtime never called it."""
        source = inspect.getsource(snapshot_builder)
        self.assertIn("backfill_outcome_evaluations", source)

    def test_02_backfill_is_importable_from_the_builder_module_path(self):
        from analysis.outcome_evaluator import backfill_outcome_evaluations as fn
        self.assertTrue(callable(fn))

    def test_03_backfill_call_sits_after_snapshot_creation(self):
        source = inspect.getsource(snapshot_builder)
        per_snapshot = source.index("run_outcome_evaluation_for_snapshot")
        backfill = source.index("backfill_outcome_evaluations")
        self.assertLess(per_snapshot, backfill)

    # --- behaviour --------------------------------------------------------

    def test_04_fresh_snapshot_alone_cannot_resolve(self):
        # Documents why the previous wiring could never work: a snapshot created now
        # has no future observations, so its horizons are unreachable.
        reference = datetime.now()
        snapshot_id = _seed_snapshot(reference)
        _seed_observation(reference, 230_000_000)
        backfill_outcome_evaluations(hours=168, horizons=[1])
        session = _test_get_session()
        rows = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == snapshot_id
        ).all()
        statuses = {r.outcome_status for r in rows}
        session.close()
        self.assertNotIn("COMPLETE", statuses)

    def test_05_matured_snapshot_resolves_on_backfill(self):
        # A snapshot from two hours ago whose +1h observation now exists.
        reference = datetime.now() - timedelta(hours=2)
        snapshot_id = _seed_snapshot(reference)
        _seed_observation(reference, 230_000_000)
        _seed_observation(reference + timedelta(hours=1), 232_000_000)
        backfill_outcome_evaluations(hours=168, horizons=[1])
        session = _test_get_session()
        row = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == snapshot_id,
            OutcomeEvaluation.horizon_hours == 1,
        ).first()
        session.close()
        self.assertIsNotNone(row)
        self.assertEqual(row.outcome_status, "COMPLETE")

    def test_06_backfill_replaces_an_earlier_insufficient_verdict(self):
        """The production case: 213 rows already recorded INSUFFICIENT_DATA."""
        reference = datetime.now() - timedelta(hours=2)
        snapshot_id = _seed_snapshot(reference)
        _seed_observation(reference, 230_000_000)

        # First pass, before the +1h observation exists.
        backfill_outcome_evaluations(hours=168, horizons=[1])
        session = _test_get_session()
        first = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == snapshot_id
        ).first()
        session.close()
        self.assertEqual(first.outcome_status, "INSUFFICIENT_DATA")

        # The observation arrives; the verdict must be revisited, not left stale.
        _seed_observation(reference + timedelta(hours=1), 232_000_000)
        backfill_outcome_evaluations(hours=168, horizons=[1])
        session = _test_get_session()
        rows = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == snapshot_id,
            OutcomeEvaluation.horizon_hours == 1,
        ).all()
        session.close()
        self.assertEqual(len(rows), 1, "must update in place, not duplicate")
        self.assertEqual(rows[0].outcome_status, "COMPLETE")

    def test_07_backfill_is_safe_to_run_repeatedly(self):
        reference = datetime.now() - timedelta(hours=2)
        snapshot_id = _seed_snapshot(reference)
        _seed_observation(reference, 230_000_000)
        _seed_observation(reference + timedelta(hours=1), 232_000_000)
        for _ in range(3):
            backfill_outcome_evaluations(hours=168, horizons=[1])
        session = _test_get_session()
        count = session.query(OutcomeEvaluation).filter(
            OutcomeEvaluation.analysis_snapshot_id == snapshot_id,
            OutcomeEvaluation.horizon_hours == 1,
        ).count()
        session.close()
        self.assertEqual(count, 1)

    def test_08_backfill_survives_an_empty_database(self):
        self.assertEqual(backfill_outcome_evaluations(hours=168, horizons=[1]), 0)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPISPC3)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 55)
    print(f"SP-C.3 KPI RESULT: {passed}/{result.testsRun} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
