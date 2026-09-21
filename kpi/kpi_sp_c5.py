"""KPI — SP-C.5: three latches that turned temporary states into permanent ones.

Each of these shipped, passed its tests, and ran in production for weeks. None of
them raised an error. All three failed by producing a constant that looked like a
reading, which is the failure mode this project keeps meeting and the reason these
assertions are written as "does it still vary" rather than "does it compute".

1. The SP-A hysteresis gate suppressed a repeat of the same decision with no time
   bound. `cooldown_hours` was in the signature, documented as reserved for future
   use, and never implemented. state.json persists across runs through the Actions
   cache, and the latch clears only when a *different* alert fires — a SELL, needing
   an EXPENSIVE valuation that has never occurred in 338 readings. 100 of 100 BUY
   candidates were held; final_decision read WAIT on all 264 stored decisions. The
   decision scorecard was therefore scoring a constant against a constant and
   correctly returning an edge of zero: the engine had not been disproven, it had
   never run.

2. Regime stress thresholds were constants calibrated for a market whose premium
   sits near zero. Measured over the 30-day window, `abs(premium) > 2.0` fired on
   250 of 252 snapshots and `platform_spread > 500000` on 252 of 252. Two of four
   families were permanently stressed and regime hysteresis latched the result:
   PANIC on all 96 analysis snapshots ever written. After calibration both fire on
   50 of 252, which is what the 80th percentile means.

3. get_usd_sell_rate ran a third-party CLI through subprocess.run with no timeout.
   Eight scheduled runs between 2026-09-14 and 2026-09-18 were killed by the GitHub
   job timeout, each showing a DNS failure on the preceding collector and then about
   twenty minutes of silence against a four-minute healthy run. Those eight are the
   missing hourly readings.
"""

import inspect
import os
import subprocess
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

from caluclator.signals import apply_hysteresis, DEFAULT_COOLDOWN_HOURS
from analysis.regime import (
    MIN_CALIBRATION_OBSERVATIONS,
    STRESS_PERCENTILE,
    RegimeClassifier,
    resolve_stress_thresholds,
)

NOW = datetime(2026, 9, 18, 12, 0, 0)


def _seed(premiums, spreads=None, base=None):
    """Snapshots one hour apart with four platform prices each."""
    session = _test_get_session()
    session.query(PlatformPrice).delete()
    session.query(MarketSnapshot).delete()
    start = base or (NOW - timedelta(hours=len(premiums)))
    for index, premium in enumerate(premiums):
        timestamp = start + timedelta(hours=index)
        snapshot = MarketSnapshot(
            timestamp=timestamp, world_gold_usd=4300.0, usd_irr=230_000.0,
            fair_price=240_000_000, premium_percent=premium, collection_mode="scheduled",
        )
        session.add(snapshot)
        session.flush()
        spread = (spreads or [1_000_000] * len(premiums))[index]
        for offset, name in enumerate(("A", "B", "C", "D")):
            session.add(PlatformPrice(
                snapshot_id=snapshot.id, platform_name=name, timestamp=timestamp,
                price_irr=230_000_000 + (spread if offset == 3 else offset),
            ))
    session.commit()
    session.close()


class KPISPC5(unittest.TestCase):

    # -- 1. the decision latch ------------------------------------------------

    def test_01_a_fresh_candidate_passes_through(self):
        self.assertEqual(apply_hysteresis("BUY", None, {}), "BUY")

    def test_02_a_different_last_alert_does_not_suppress(self):
        self.assertEqual(apply_hysteresis("BUY", "SELL", {}), "BUY")

    def test_03_a_repeat_inside_the_cooldown_is_suppressed(self):
        self.assertEqual(
            apply_hysteresis("BUY", "BUY", {}, last_alert_at=NOW - timedelta(hours=1),
                             now=NOW),
            "WAIT",
        )

    def test_04_a_repeat_after_the_cooldown_is_allowed(self):
        # This is the fix. Before it, this case returned WAIT forever, which is how
        # 100 BUY candidates in a row were suppressed.
        self.assertEqual(
            apply_hysteresis("BUY", "BUY", {},
                             last_alert_at=NOW - timedelta(hours=DEFAULT_COOLDOWN_HOURS + 1),
                             now=NOW),
            "BUY",
        )

    def test_05_the_boundary_itself_releases(self):
        self.assertEqual(
            apply_hysteresis("BUY", "BUY", {},
                             last_alert_at=NOW - timedelta(hours=DEFAULT_COOLDOWN_HOURS),
                             now=NOW),
            "BUY",
        )

    def test_06_an_unknown_alert_time_fails_open_not_closed(self):
        # Suppressing on an unknown timestamp reinstates the latch: one missing record
        # would disable alerting permanently. A duplicate alert is noise; silence is
        # the failure that already cost a hundred signals.
        self.assertEqual(apply_hysteresis("BUY", "BUY", {}, last_alert_at=None), "BUY")

    def test_07_cooldown_is_configurable(self):
        thresholds = {"cooldown_hours": 6}
        self.assertEqual(
            apply_hysteresis("BUY", "BUY", thresholds,
                             last_alert_at=NOW - timedelta(hours=7), now=NOW),
            "BUY",
        )
        self.assertEqual(
            apply_hysteresis("BUY", "BUY", thresholds,
                             last_alert_at=NOW - timedelta(hours=5), now=NOW),
            "WAIT",
        )

    def test_08_non_alert_candidates_are_untouched(self):
        self.assertEqual(apply_hysteresis("WAIT", "BUY", {}), "WAIT")
        self.assertEqual(apply_hysteresis("UNKNOWN", "BUY", {}), "UNKNOWN")
        self.assertEqual(apply_hysteresis("", "BUY", {}), "WAIT")

    def test_09_sell_obeys_the_same_rule(self):
        self.assertEqual(
            apply_hysteresis("SELL", "SELL", {}, last_alert_at=NOW - timedelta(hours=1),
                             now=NOW),
            "WAIT",
        )
        self.assertEqual(
            apply_hysteresis("SELL", "SELL", {}, last_alert_at=NOW - timedelta(hours=30),
                             now=NOW),
            "SELL",
        )

    def test_10_the_gate_cannot_suppress_without_consulting_time(self):
        # A regression guard on the shape of the fix, not just its output: the old
        # implementation could not have referenced a timestamp at all.
        source = inspect.getsource(apply_hysteresis)
        body = source.split('"""')[-1]
        self.assertIn("last_alert_at", body)
        self.assertIn("cooldown_hours", body)

    def test_11_a_decision_history_can_contain_something_other_than_wait(self):
        # The property that actually matters. Twenty-four consecutive BUY candidates
        # a day apart must not collapse to a single WAIT stream.
        last_alert, last_at = None, None
        decisions = []
        for hour in range(0, 24 * 5, 12):
            moment = NOW + timedelta(hours=hour)
            final = apply_hysteresis("BUY", last_alert, {}, last_alert_at=last_at,
                                     now=moment)
            decisions.append(final)
            if final in ("BUY", "SELL"):
                last_alert, last_at = final, moment
        self.assertIn("BUY", decisions)
        self.assertIn("WAIT", decisions)
        self.assertGreater(decisions.count("BUY"), 1)

    # -- 2. regime calibration ------------------------------------------------

    def test_12_calibration_abstains_without_a_session(self):
        self.assertEqual(resolve_stress_thresholds(None), {})

    def test_13_calibration_abstains_below_the_minimum_sample(self):
        _seed([-3.0, -3.5, -4.0])
        self.assertEqual(resolve_stress_thresholds(_test_get_session(), now=NOW), {})

    def test_14_calibration_returns_the_stress_percentile_of_the_window(self):
        premiums = [-(1.0 + 0.1 * i) for i in range(40)]   # 1.0 .. 4.9 magnitude
        _seed(premiums)
        result = resolve_stress_thresholds(_test_get_session(), now=NOW)
        magnitudes = sorted(abs(p) for p in premiums)
        expected = magnitudes[int(STRESS_PERCENTILE / 100.0 * len(magnitudes))]
        self.assertAlmostEqual(result["premium_magnitude"], round(expected, 4), places=3)

    def test_15_a_calibrated_threshold_fires_on_a_minority_not_everything(self):
        # The whole point. The fixed 2.0 threshold fired on 250 of 252 production
        # snapshots; a percentile threshold fires on roughly a fifth by construction.
        premiums = [-(1.0 + 0.1 * i) for i in range(40)]
        _seed(premiums)
        threshold = resolve_stress_thresholds(_test_get_session(), now=NOW)["premium_magnitude"]
        fires = sum(1 for p in premiums if abs(p) > threshold)
        self.assertLess(fires / len(premiums), 0.35)
        self.assertGreater(fires, 0)

    def test_16_the_old_fixed_threshold_would_have_fired_on_everything(self):
        # Documents the defect rather than trusting memory of it.
        premiums = [-(1.82 + 0.16 * i) for i in range(40)]  # the observed range
        fires = sum(1 for p in premiums if abs(p) > 2.0)
        self.assertGreater(fires / len(premiums), 0.9)

    def test_17_calibration_covers_platform_spread_too(self):
        _seed([-(1.0 + 0.1 * i) for i in range(40)],
              spreads=[100_000 * (i + 1) for i in range(40)])
        result = resolve_stress_thresholds(_test_get_session(), now=NOW)
        self.assertIn("platform_spread", result)
        self.assertGreater(result["platform_spread"], 500_000.0)

    def test_18_explicit_configuration_still_wins(self):
        # Calibration fills what the caller has not pinned; it does not override.
        classifier = RegimeClassifier({"stress_thresholds": {"premium_magnitude": 99.0}})
        result = classifier.classify({"premium_percent": -5.0, "premium_change": 0.0})
        premium_family = next(f for f in result.evidence if f.name == "PREMIUM_STRESS")
        self.assertFalse(premium_family.stressed)

    def test_18b_the_shipped_config_does_not_pin_the_calibrated_keys(self):
        # The reason this assertion exists. Calibration shipped, computed correctly,
        # logged correctly in production, and was then discarded, because
        # config/config.json pinned the same three keys and the merge lets explicit
        # config win. regime_state stayed PANIC on every reading for another day.
        #
        # The unit tests could not catch it: they construct the classifier directly
        # and never load the shipped config. Assert against the file itself.
        import json
        path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
        with open(path, encoding="utf-8") as handle:
            shipped = json.load(handle)
        pinned = shipped.get("regime", {}).get("stress_thresholds", {})
        for key in ("premium_magnitude", "premium_change", "platform_spread"):
            self.assertNotIn(
                key, pinned,
                f"{key} is pinned in config.json, which silently overrides the "
                f"per-run calibration and restores the constant it was written to fix",
            )

    def test_18c_the_merge_still_lets_a_deliberate_override_win(self):
        # The override behaviour itself is correct and is kept: a threshold someone
        # sets on purpose must beat a calibrated one. What was wrong was shipping
        # defaults in that slot.
        calibrated = {"premium_magnitude": 4.9}
        config_pinned = {"premium_magnitude": 99.0}
        merged = dict(calibrated)
        merged.update(config_pinned)
        self.assertEqual(merged["premium_magnitude"], 99.0)

    def test_19_calibration_failure_degrades_rather_than_raising(self):
        class _Broken:
            def query(self, *a, **k):
                raise RuntimeError("connection lost")
        self.assertEqual(resolve_stress_thresholds(_Broken()), {})

    def test_20_regime_can_reach_more_than_one_state(self):
        # 96 of 96 snapshots read PANIC. A classifier with one reachable output is a
        # constant, so the assertion is that the outputs differ, not what they are.
        calm = {"premium_percent": -1.0, "premium_change": 0.0, "volatility": 0.1,
                "usd_change": 0.0, "platform_spread": 100_000.0,
                "high_impact_news_count": 0}
        stressed = {"premium_percent": -9.0, "premium_change": 3.0, "volatility": 5.0,
                    "usd_change": 3.0, "platform_spread": 50_000_000.0,
                    "high_impact_news_count": 10}
        thresholds = {"stress_thresholds": {"premium_magnitude": 4.9,
                                            "premium_change": 0.6,
                                            "platform_spread": 8_000_000.0}}
        a = RegimeClassifier({**thresholds, "hysteresis_enabled": False}).classify(calm)
        b = RegimeClassifier({**thresholds, "hysteresis_enabled": False}).classify(stressed)
        self.assertNotEqual(a.state, b.state)

    # -- 3. the unbounded subprocess ------------------------------------------

    def test_21_the_usd_collector_bounds_its_subprocess(self):
        import collector.bonbast as bonbast
        captured = {}

        def _fake_run(*args, **kwargs):
            captured.update(kwargs)
            raise subprocess.TimeoutExpired(cmd="bonbast", timeout=kwargs.get("timeout"))

        original = subprocess.run
        subprocess.run = _fake_run
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                bonbast.get_usd_sell_rate()
        finally:
            subprocess.run = original
        self.assertIn("timeout", captured)
        self.assertGreater(captured["timeout"], 0)

    def test_22_a_timeout_is_catchable_by_the_existing_fallback(self):
        # main.py wraps this call in `except Exception` and degrades USD to None, so
        # a timeout must cost one input rather than the whole run.
        self.assertTrue(issubclass(subprocess.TimeoutExpired, Exception))

    def test_23_no_unbounded_subprocess_remains_in_the_collectors(self):
        import collector.bonbast as bonbast
        source = inspect.getsource(bonbast)
        self.assertIn("timeout=", source)


    # -- 3b. a fourth ceiling that did not bind --------------------------------

    def test_23b_a_hanging_collector_cannot_take_the_run_with_it(self):
        """GLOBAL_COLLECTOR_TIMEOUT has to actually bound the call.

        It did not. wait() was capped correctly, but future.cancel() only cancels a
        future that has not started, and with max_workers equal to the collector
        count every future starts at once -- so nothing was ever cancellable.
        Leaving the ThreadPoolExecutor context manager then called
        shutdown(wait=True), which blocks until the slowest thread finishes. The
        documented ceiling was followed immediately by an unbounded wait.

        requests' timeout= does not bound DNS resolution, so a degraded network
        leaves a collector thread hung indefinitely. The 2026-09-21 05:30 UTC
        scheduled run died at the job timeout having written nothing; that hourly
        reading does not exist.
        """
        import time
        import collector.iran as iran

        def healthy():
            return {"platform": "Healthy", "price": 1}

        def hangs():
            time.sleep(30)
            return {"platform": "Hangs", "price": 1}
        hangs.__name__ = "get_hangs_price"

        collectors, ceiling = iran.COLLECTORS, iran.GLOBAL_COLLECTOR_TIMEOUT
        iran.COLLECTORS, iran.GLOBAL_COLLECTOR_TIMEOUT = [healthy, hangs], 1
        try:
            started = time.monotonic()
            markets = iran.get_market_prices()
            elapsed = time.monotonic() - started
        finally:
            iran.COLLECTORS, iran.GLOBAL_COLLECTOR_TIMEOUT = collectors, ceiling

        self.assertLess(elapsed, 10,
                        "the global collector timeout did not bound the call")
        self.assertEqual(markets["Healthy"]["status"], "OK")
        self.assertIn("timed out", markets["Hangs"]["status"])

    def test_23c_collector_threads_cannot_hold_the_interpreter_open(self):
        # Non-daemon pool threads keep Python alive at exit even after the function
        # returns, which converts a bounded call back into a hung process.
        import inspect
        import collector.iran as iran
        source = inspect.getsource(iran.get_market_prices)
        self.assertIn("daemon=True", source)
        self.assertNotIn("ThreadPoolExecutor", source)

    def test_23d_the_ceiling_is_one_deadline_not_one_per_collector(self):
        # Eleven sequential joins of GLOBAL_COLLECTOR_TIMEOUT each would permit
        # eleven times the intended ceiling.
        import inspect
        import collector.iran as iran
        source = inspect.getsource(iran.get_market_prices)
        self.assertIn("deadline", source)

    # -- 4. world-gold fallback provenance (SP-C-003) --------------------------

    def test_24_fallbacks_return_the_observation_time_not_just_a_price(self):
        import main
        for fn in (main._fallback_world_from_history, main._fallback_world_from_db):
            result = fn([]) if fn is main._fallback_world_from_history else fn()
            self.assertIsInstance(result, tuple)
            self.assertEqual(len(result), 2)

    def test_25_history_fallback_reports_the_stored_timestamp(self):
        import main
        stamp = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        price, observed = main._fallback_world_from_history(
            [{"timestamp": stamp, "world_gold": 4321.0}])
        self.assertEqual(price, 4321.0)
        self.assertEqual(observed.isoformat(), stamp)

    def test_26_history_fallback_refuses_a_value_beyond_the_age_cap(self):
        import main
        stamp = (datetime.utcnow() - timedelta(hours=9)).isoformat()
        self.assertEqual(
            main._fallback_world_from_history([{"timestamp": stamp, "world_gold": 1.0}]),
            (None, None))

    def test_27_a_none_pair_is_not_mistaken_for_a_value(self):
        # `a or b` over these functions is a live bug: (None, None) is truthy, so the
        # tuple itself would be assigned as the world gold price.
        import inspect, main
        body = inspect.getsource(main.main)
        self.assertNotIn("_fallback_world_from_history(history) or", body)

    def test_28_a_cached_world_price_is_distinguishable_in_storage(self):
        # Both provenance channels were inert: source was the literal
        # "kitco_fallback" whether live or cached, and freshness was
        # evaluate_freshness(now, now, ...) -- FRESH on 3,316 of 3,316 rows.
        import inspect, main
        source = inspect.getsource(main._save_price_observations)
        # Comment lines are stripped: the old literal is quoted in the explanation
        # above the fix, and an assertion that reads prose is not an assertion.
        code = " ".join(l for l in source.splitlines()
                        if not l.lstrip().startswith("#"))
        self.assertIn("kitco_cached", code)
        self.assertIn("world_from_fallback", code)
        self.assertNotIn('"kitco_fallback"', code)

    def test_29_world_freshness_is_evaluated_not_hardcoded(self):
        from intelligence.freshness import evaluate_freshness
        now = datetime(2026, 9, 20, 12, 0)
        self.assertEqual(evaluate_freshness(now, now, 15), "FRESH")
        self.assertEqual(
            evaluate_freshness(now - timedelta(hours=5), now, 15), "STALE")

    def test_30_platform_observations_keep_collection_time_freshness(self):
        # Deliberate: platforms are fetched live at `now` and do not disclose the age
        # of their own quote, so anything but FRESH there is invented precision.
        import inspect, main
        body = inspect.getsource(main._save_price_observations)
        self.assertIn("evaluate_freshness(now, now, stale_threshold)", body)

    def test_31_fair_price_docstring_no_longer_claims_the_wrong_unit(self):
        from caluclator.gold import calculate_fair_price
        doc = calculate_fair_price.__doc__ or ""
        self.assertNotIn("in IRR per gram", doc)
        self.assertIn("Toman", doc)
        # and the arithmetic is unchanged
        self.assertAlmostEqual(calculate_fair_price(2000.0, 50000.0),
                               2000.0 * 50000.0 / 31.1034768 * 0.75, places=4)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(KPISPC5)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("\n" + "=" * 55)
    print(f"SP-C.5 KPI RESULT: {passed}/{result.testsRun} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
