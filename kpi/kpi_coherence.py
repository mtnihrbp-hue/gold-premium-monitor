"""KPI - cross-cutting coherence.

Every other KPI file checks one module or one surface against the market. This one
checks modules and surfaces **against each other**, because that is where this
project's defects actually live.

The case that produced this file: on 2026-09-21 `Deep discount` meant 3.29% in UPDATE
and 3.70% in ANALYZE and the push. Each surface was correct on its own, each had
passing KPIs, and the contradiction existed only in the space between them. It was
caught by a human reading three production messages side by side. Nothing in a suite
of 25 files landed on it, and nothing would have, because an assertion that spans two
modules has to be written on purpose.

Auditing for that one defect then turned up three more of the same shape, all older,
and this file was written before any of them were fixed:

    valuation_state was CHEAP on 364 of 364 rows (fixed threshold) while the
    percentile band stored in the same row read EXPENSIVE on 54 of 134
    -- closed in SP-C.15, both now come from one classifier

    caluclator/valuation.py read config keys `buy_premium` / `sell_premium`,
    which do not exist -- config.json defines `buy_premium_percent` /
    `sell_premium_percent` -- so it silently used its own defaults and the
    configured sell threshold of 3.0 had never been in effect
    -- closed in SP-C.15

    valuation_context_json is computed and persisted on every run and nothing
    in src/ reads it
    -- still registered, now as a deliberate audit record

Two of the three closed on the first change made after this file existed, and closing
them failed the suite until their register entries were retired. That is the intended
behaviour, not a nuisance: see below.

--------------------------------------------------------------------------------
The register
--------------------------------------------------------------------------------

Divergences that are known and accepted live in `ACCEPTED` below. They are not
silence: every entry names the two things that disagree, why the gap is tolerated,
and the document that records it, and `test_30` onwards enforce all three.

Critically, an entry whose divergence has been **fixed** makes this file fail. A
register that can quietly go stale is a second copy of the problem it exists to
prevent -- which is exactly how `PROJECT_MEMORY.md` came to record
`valuation_state read CHEAP on every reading` as resolved on 2026-09-15 while
production kept writing CHEAP every hour.
"""

import inspect
import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC_DIR)

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"

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

from analysis import analyze_report as ar
from analysis import bubble_position as bp
from analysis import push_trigger as pt
from caluclator.valuation import classify_valuation

NOW = datetime(2026, 9, 21, 12, 0, 0)
FAIR = 240_000_000

# The shape of the real record, 2026-09-21: 437 readings, every one a discount,
# sizes from 0.83% to 5.40%, median 3.12%. Classifiers are exercised against this
# rather than against a tidy synthetic spread, because a classifier that looks
# healthy on a uniform sample and collapses on the real one is the exact failure
# this project has shipped four times.
PRODUCTION_SHAPE = [0.83, 1.20, 1.55, 1.90, 2.10, 2.35, 2.50, 2.68, 2.80, 2.95,
                    3.05, 3.12, 3.20, 3.30, 3.42, 3.55, 3.64, 3.70, 3.85, 4.00,
                    4.20, 4.45, 4.70, 4.90, 5.05, 5.40]

# The same market on the *stored* basis: premium_percent is computed from the single
# cheapest platform, so it runs deeper -- -8.19% to -1.52% across all 438 rows. It is
# a separate constant because the decision leg ranks the stored column while
# every displayed figure comes from the trimmed basis, and feeding a classifier the
# wrong one of the two is itself the divergence this file is about.
#
# Note where the -1.5 buy threshold falls against that range: outside it. Zero of 438
# readings are shallower. The boundary has never been crossed.
STORED_PREMIUM_SHAPE = [-1.52, -1.70, -1.95, -2.20, -2.48, -2.75, -3.00, -3.28,
                        -3.55, -3.80, -4.10, -4.40, -4.75, -5.10, -5.50, -6.00,
                        -6.55, -7.10, -7.60, -8.19]


# ---------------------------------------------------------------------------
# The register of accepted divergences
# ---------------------------------------------------------------------------

ACCEPTED = {
    "valuation_context_unwired": {
        "what": "market_states.valuation_context_json is written every run and "
                "read by nothing in src/",
        "why": "Deliberately an audit record rather than an input. It captures what "
               "the system knew when a decision was made so the scorecard can "
               "attribute an outcome later; a consumer inside src/ would make the "
               "decision depend on its own audit trail.",
        "doc": ("SP_C_HANDOFF.md", "26.6"),
    },
    "displayed_gap_vs_stored_premium": {
        "what": "the discount shown to a reader (mean of the 3 cheapest) against "
                "market_snapshots.premium_percent (single cheapest)",
        "why": "Deliberate and long-standing. Changing the stored column "
               "invalidates 177 analysis snapshots and 525 outcome evaluations, "
               "so it is its own phase with its own backfill.",
        "doc": ("SP_C_HANDOFF.md", "15.1"),
    },
    "threshold_pool_vs_ranking_pool": {
        "what": "the deep-discount level is drawn from the settled non-user pool; "
                "`Bigger than X%` ranks against the scheduled-preferred pool",
        "why": "Ranking and thresholding answer different questions and only the "
               "threshold is acted on. Unifying would drop the agreed scheduled "
               "gate or cut ANALYZE's episode sample from 265 readings to 99.",
        "doc": ("SP_C_HANDOFF.md", "24.4"),
    },
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _seed(readings):
    session = _test_get_session()
    session.query(PlatformPrice).delete()
    session.query(MarketSnapshot).delete()
    for timestamp, mode, size in readings:
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
    base = start or (NOW - timedelta(hours=len(sizes) + 14))
    return [(base + timedelta(hours=i), mode, v) for i, v in enumerate(sizes)]


def _python_files(*subdirs):
    roots = [SRC / d for d in subdirs] if subdirs else [SRC]
    for root in roots:
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            yield path


def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def _code(path):
    """The file with comments and string literals removed.

    Scanning raw text for a symbol counts the prose that discusses it. The first
    version of `test_25` reported `valuation_context_json` as wired because a
    docstring in `caluclator/valuation.py` explains why it is not -- a test passing
    for the exact reason it exists to catch. This file is about assertions that span
    modules; an assertion that cannot tell code from a comment spans nothing.
    """
    import io as _io
    import tokenize as _tokenize

    source = _read(path)
    kept = []
    try:
        for token in _tokenize.generate_tokens(_io.StringIO(source).readline):
            if token.type in (_tokenize.COMMENT, _tokenize.STRING):
                continue
            kept.append(token.string)
    except (_tokenize.TokenError, IndentationError, SyntaxError):
        return source
    return "\n".join(kept)


def _config():
    return json.loads((REPO / "config" / "config.json").read_text(encoding="utf-8"))


class KPICoherence(unittest.TestCase):

    # -- 1. one concept, one definition ---------------------------------------

    def test_01_the_deep_level_has_one_definition(self):
        """UPDATE, ANALYZE and the push must not each own a rank. They did, and the
        same two words carried 3.29% and 3.70% on 2026-09-21."""
        self.assertEqual(ar.DEEP_ZONE_PERCENTILE, bp.DEEP_DISCOUNT_PERCENTILE)
        self.assertEqual(pt.FIRE_PERCENTILE, bp.DEEP_DISCOUNT_PERCENTILE)

    def test_02_equal_constants_are_not_enough_each_must_call_the_resolver(self):
        """Three constants that agree are three definitions that currently agree.
        Each surface has to reach the same function."""
        self.assertIn("deep_discount_threshold(reference_readings(",
                      inspect.getsource(bp.resolve_relative_valuation))
        self.assertIn("deep_discount_threshold(series)",
                      inspect.getsource(pt.resolve_push_thresholds))
        self.assertIn("deep_discount_threshold(series)",
                      inspect.getsource(ar.resolve_deep_zone))

    def test_03_the_three_surfaces_resolve_to_the_same_number(self):
        """The assertion that would have caught the defect. One dataset, three
        surfaces, one value."""
        _seed(_hourly(PRODUCTION_SHAPE * 3))
        session = _test_get_session()
        end = ar.to_utc(datetime.combine(ar.local_date(NOW), datetime.min.time()))
        pool = bp.reference_readings(
            bp.basis_series(session, end - timedelta(days=30), NOW), end)

        shared = bp.deep_discount_threshold(pool)
        zone = ar.resolve_deep_zone(session, current_gap=-3.0, now=NOW).threshold
        fire = pt.resolve_push_thresholds(session, now=NOW).fire_at

        self.assertIsNotNone(shared)
        self.assertAlmostEqual(shared, zone, places=9)
        self.assertAlmostEqual(shared, fire, places=9)

    def test_04_update_prints_the_number_the_push_acts_on(self):
        """The rule this file exists to enforce: the number a reader is shown is the
        number the system acts on."""
        _seed(_hourly(PRODUCTION_SHAPE * 3))
        session = _test_get_session()
        valuation = bp.resolve_relative_valuation(
            session,
            markets={n: {"price": FAIR * 0.97, "status": "OK"} for n in "ABC"},
            fair_price=FAIR, now=NOW)
        fire = pt.resolve_push_thresholds(session, now=NOW).fire_at
        self.assertEqual(valuation.status, "OK")
        self.assertAlmostEqual(valuation.deep_at, fire, places=9)

    def test_05_no_module_keeps_its_own_copy_of_a_shared_formula(self):
        """`analyze_report._percentile` was a byte-identical copy of
        `bubble_position._value_at_percentile`. One concept, two definitions, is the
        shape every disagreement in this system has started as."""
        idiom = re.compile(r"int\(\s*percentile\s*/\s*100")
        owners = []
        for path in _python_files("analysis", "caluclator", "alerts"):
            body = _read(path)
            for match in re.finditer(r"^def (\w+)\(.*?(?=^def |\Z)",
                                     body, re.S | re.M):
                if idiom.search(match.group(0)):
                    owners.append(f"{path.stem}.{match.group(1)}")
        self.assertEqual(sorted(owners), ["bubble_position._value_at_percentile"],
                         f"the percentile formula is defined in more than one "
                         f"place: {owners}")

    # -- 2. configuration actually reaching the code --------------------------

    def test_10_every_threshold_key_the_code_reads_exists_in_config(self):
        """A key that does not exist falls back to a hardcoded default in silence.
        `caluclator/valuation.py` reads `sell_premium`, config defines
        `sell_premium_percent`, and the configured 3.0 has never been in effect --
        editing config.json does nothing to it."""
        # Scoped to caluclator/, which is where the dict genuinely is
        # config["thresholds"]. analysis/regime.py also calls `thresholds.get`, but
        # on its own calibrated stress dict -- a different object with different
        # keys, and counting it here would be a false positive.
        configured = set(_config().get("thresholds", {}))
        pattern = re.compile(r"thresholds\.get\(\s*[\"'](\w+)[\"']")
        missing = {}
        for path in _python_files("caluclator"):
            for key in pattern.findall(_code(path)):
                if key not in configured:
                    missing.setdefault(path.name, set()).add(key)

        self.assertEqual({k: sorted(v) for k, v in missing.items()}, {},
                         "a module reads a threshold key config does not define")

    def test_11_the_configured_bounds_actually_reach_the_classifier(self):
        """Not enough that the keys exist -- the values must change the answer.
        `sell_premium_percent` was 3.0 in config and 2.0 in effect for months,
        because the lookup missed and fell through to a hardcoded default."""
        thresholds = _config()["thresholds"]
        sell_at = thresholds["sell_premium_percent"]
        kw = dict(cheap_rank=40, expensive_rank=80,
                  buy_at=thresholds["buy_premium_percent"])
        self.assertEqual(
            classify_valuation(95, sell_at, sell_at=sell_at, **kw), "EXPENSIVE")
        self.assertEqual(
            classify_valuation(95, sell_at - 0.01, sell_at=sell_at, **kw), "FAIR",
            "the configured sell threshold does not bind")

    # -- 3. two classifiers of one concept ------------------------------------

    def test_12_the_valuation_leg_is_not_a_constant(self):
        """The repo's own rule, made executable. This column read CHEAP on 364 of
        364 rows because its threshold sat 0.02 pp outside the observed range of
        438 readings, and no test noticed for months."""
        thresholds = _config()["thresholds"]
        ordered = sorted(STORED_PREMIUM_SHAPE)
        states = {
            classify_valuation(
                bp._percentile_of(value, ordered), value,
                cheap_rank=bp.CHEAP_PERCENTILE,
                expensive_rank=bp.EXPENSIVE_PERCENTILE,
                buy_at=thresholds["buy_premium_percent"],
                sell_at=thresholds["sell_premium_percent"])
            for value in ordered
        }
        self.assertGreater(len(states), 1,
                           "the valuation leg is a constant over the real record")
        self.assertIn("CHEAP", states)
        self.assertIn("FAIR", states)

    def test_13_a_discount_is_never_labelled_expensive(self):
        """EXPENSIVE asserts the market is above fair value, and the conflict matrix
        turns EXPENSIVE + WEAKENING into SELL. On rank alone this engine would have
        issued SELL on a market trading 1.5% below fair value."""
        thresholds = _config()["thresholds"]
        ordered = sorted(STORED_PREMIUM_SHAPE)
        for value in ordered:
            state = classify_valuation(
                bp._percentile_of(value, ordered), value,
                cheap_rank=bp.CHEAP_PERCENTILE,
                expensive_rank=bp.EXPENSIVE_PERCENTILE,
                buy_at=thresholds["buy_premium_percent"],
                sell_at=thresholds["sell_premium_percent"])
            if value < 0:
                self.assertNotEqual(state, "EXPENSIVE", f"{value} is a discount")

    def test_14_one_reading_cannot_carry_two_valuations(self):
        """`valuation_state` and the band in `valuation_context_json` labelled the
        same row and disagreed on 114 of 134 -- CHEAP in the column, EXPENSIVE in
        the JSON, the same moment. Both now come from one function."""
        self.assertIn("classify_valuation(",
                      inspect.getsource(bp._classify_band),
                      "the band must delegate, not classify")
        self.assertIn("classify_valuation(",
                      inspect.getsource(bp.resolve_decision_valuation),
                      "the decision leg must delegate, not classify")
        self.assertNotIn("evaluate_valuation",
                         _read(SRC / "caluclator" / "signal_state.py"),
                         "the fixed-threshold classifier is back in the pipeline")

    def test_15_the_valuation_leg_abstains_rather_than_guessing(self):
        """There is deliberately no fixed-threshold fallback. A fallback that always
        answers is how this leg became a constant."""
        _seed(_hourly([2.0, 2.5, 3.0]))
        result = bp.resolve_decision_valuation(
            _test_get_session(), -3.0, _config()["thresholds"], now=NOW)
        self.assertEqual(result.state, "UNKNOWN")
        self.assertEqual(result.status, "INSUFFICIENT_DATA")
        from caluclator.conflict import evaluate_conflict
        self.assertEqual(
            evaluate_conflict("UNKNOWN", "IMPROVING", "DISCOUNT_DOMINANT")[1],
            "UNKNOWN", "an unknown valuation must abstain, not default to WAIT")

    def test_16_the_valuation_reference_is_settled_and_excludes_user_rows(self):
        """Same discipline as the deep-discount level. A reference containing today
        moves under the reading being measured, and the reader pressing Update must
        not move the level the decision engine is judged against."""
        source = inspect.getsource(bp.resolve_decision_valuation)
        self.assertIn("reference_readings(series, reference_end)", source)
        self.assertIn("local_date(now)", source)

    def test_17_the_leg_and_the_reader_rank_on_their_own_basis(self):
        """The decision leg ranks the stored min-based premium against a window of
        stored min-based premiums. Ranking it against the trimmed-basis window every
        displayed figure uses would move it 0.55 pp on median with no market
        movement -- LESSONS_LEARNED section 8."""
        source = inspect.getsource(bp.resolve_decision_valuation)
        self.assertIn("stored_premium_series(", source)
        self.assertNotIn("basis_series(", source)

    # -- 4. a direction claim needs a direction -------------------------------

    def test_20_a_magnitude_never_carries_a_direction_claim(self):
        """`evaluate_push` compared abs(gap), so a premium would have alerted under
        the heading DEEP DISCOUNT. Latent only because all 437 readings on record are
        discounts -- the sample held no counterexample, so nothing could expose it."""
        thresholds = pt.PushThresholds(fire_at=3.7, rearm_at=3.2, band_pp=0.5,
                                       noise_pp=0.33, sample_size=200, status="OK")
        self.assertTrue(pt.evaluate_push(-4.5, thresholds, armed=True).should_fire)
        premium = pt.evaluate_push(+4.5, thresholds, armed=True)
        self.assertFalse(premium.should_fire)
        self.assertEqual(premium.reason, "NOT_A_DISCOUNT")

    def test_21_rearming_stays_sign_blind(self):
        """Fail-open. A gate held closed that then meets a premium must re-arm, or
        the market can return to a deep discount and find it still shut."""
        held = pt.evaluate_push(
            +4.5, pt.PushThresholds(fire_at=3.7, rearm_at=3.2, band_pp=0.5,
                                    noise_pp=0.33, sample_size=200, status="OK"),
            armed=False)
        self.assertTrue(held.armed_after)

    def test_22_a_threshold_compared_against_readings_is_never_rounded(self):
        """Gaps land on values like 8.999999999999996. Rounding the level to 9.0
        lifted it above its own source readings and a zone containing eight of them
        measured zero episodes."""
        base = datetime(2026, 9, 1)
        quiet = [(base + timedelta(hours=i), "scheduled", -2.0000000000000018)
                 for i in range(30)]
        deep = [(base + timedelta(hours=40 + i), "scheduled", -8.999999999999996)
                for i in range(8)]
        level = bp.deep_discount_threshold(quiet + deep)
        self.assertEqual(len([g for _, _, g in deep if abs(g) >= level]), 8)

    # -- 5. computed and persisted means consumed -----------------------------

    def test_25_a_persisted_analysis_artifact_has_a_consumer(self):
        """Built but not wired, nine times before this. A value computed on every run
        and read by nothing is a fix that was never applied."""
        writers = {"models.py", "repository.py", "main.py"}
        unwired = []
        for column in ("valuation_context_json",):
            # An attribute read or a key lookup, not a bare mention. The first
            # version of this test counted the prose in two docstrings that discuss
            # the column as consumers of it, and passed for the wrong reason.
            access = re.compile(rf"""\.{column}\b|\[\s*["']{column}["']\s*\]""")
            readers = [p.name for p in _python_files()
                       if access.search(_code(p)) and p.name not in writers]
            if not readers:
                unwired.append(column)
        expected = (["valuation_context_json"]
                    if "valuation_context_unwired" in ACCEPTED else [])
        self.assertEqual(unwired, expected,
                         "a persisted analysis artifact has no consumer")

    # -- 6. the register must stay honest -------------------------------------

    def test_30_every_accepted_divergence_names_both_sides_and_a_reason(self):
        for key, entry in ACCEPTED.items():
            self.assertTrue(entry.get("what"), f"{key} does not say what diverges")
            self.assertTrue(entry.get("why"), f"{key} does not say why it is accepted")
            self.assertGreater(len(entry["why"]), 40,
                               f"{key}: 'why' is too short to be a reason")

    def test_31_every_accepted_divergence_cites_a_document_that_says_so(self):
        """An entry without a document is a defect with better manners."""
        for key, entry in ACCEPTED.items():
            filename, marker = entry["doc"]
            path = REPO / filename
            self.assertTrue(path.exists(), f"{key} cites a missing file {filename}")
            self.assertIn(marker, _read(path),
                          f"{key} cites {filename} '{marker}', which is not there")

    def test_32_the_register_is_not_a_dumping_ground(self):
        """Not a hard limit on correctness, a limit on drift. If this fails, the
        answer is to close entries, not to raise the number."""
        self.assertLessEqual(len(ACCEPTED), 8,
                             "accepted divergences are accumulating faster than "
                             "they are being closed")


if __name__ == "__main__":
    print("=" * 55)
    print("CROSS-CUTTING COHERENCE")
    print("=" * 55)
    for key, entry in ACCEPTED.items():
        print(f"  accepted divergence: {key}")
        print(f"      {entry['what']}")
        print(f"      recorded in {entry['doc'][0]} ({entry['doc'][1]})")
    print()
    suite = unittest.TestLoader().loadTestsFromTestCase(KPICoherence)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print()
    print("=" * 55)
    print(f"COHERENCE KPI RESULT: {passed}/{total} PASS")
    print("=" * 55)
    sys.exit(0 if result.wasSuccessful() else 1)
