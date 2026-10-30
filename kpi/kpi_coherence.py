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
    "structure_leg_fires_rarely": {
        "what": "market_states.structure_state is DISCOUNT_DOMINANT on 365 of 367 "
                "rows -- a rare-event detector rather than a classifier that "
                "separates the typical reading",
        "why": "Deliberately left alone. Measured over 440 snapshots, the three "
               "candidate replacements (platform spread, cheapest-to-median gap, "
               "breadth) all sit within one standard error of chance at z = -0.98, "
               "0.07 and 1.40, while the incumbent separates at z = -2.04 on the "
               "seven days it does fire. Replacing a leg of the decision matrix "
               "with a measured non-signal would be worse than leaving a rare one "
               "in place. Review when the non-DISCOUNT_DOMINANT count reaches 30.",
        "doc": ("SP_C_HANDOFF.md", "28.1"),
    },
    "news_llm_path_never_ran": {
        "what": "news_events.classification_method is KEYWORD on all 1441 rows; "
                "the LLM classification path has never executed",
        "why": "The keyword rules were repaired in SP-C.16 and now abstain honestly "
               "rather than mislabel. Whether an LLM layer is wired at all is a "
               "product decision with a cost attached, and "
               "skills/llm-news-intelligence.md forbids it acquiring any "
               "calculation or decision authority regardless.",
        "doc": ("SP_C_HANDOFF.md", "27.5"),
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


def _calls_and_rebinds(source):
    """The functions a file calls, and the names it rebinds: assignment targets
    (each element of a tuple assignment too) and the targets of `patch(...)`.

    Read from the syntax tree, not the text. `test_27` matched text against
    `_code`, whose tokens are joined by newlines, so `get_invi_price(` never
    matched and the test could not fail (SP_D_HANDOFF.md 37.8).
    """
    import ast as _ast

    calls, rebinds = set(), set()
    for node in _ast.walk(_ast.parse(source)):
        if isinstance(node, _ast.Call):
            func = node.func
            name = func.attr if isinstance(func, _ast.Attribute) else getattr(func, "id", "")
            calls.add(name)
            if name == "patch" and node.args and isinstance(node.args[0], _ast.Constant):
                rebinds.add(str(node.args[0].value))
        elif isinstance(node, _ast.Assign):
            for target in node.targets:
                for element in (target.elts if isinstance(target, _ast.Tuple) else [target]):
                    rebinds.add(_ast.unparse(element))
    return calls, rebinds


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

    def test_18_every_ranked_quantity_uses_the_settled_pool(self):
        """`resolve_bubble_position` ranked against a window that ran to `now`,
        counted the reader's own clicks, and read the machine clock -- the SP-C.5
        and SP-C.7 defects, fixed once in a sibling function and never back-ported.
        Nothing decided on it, but it fed the audit record that accompanies the
        decision, so the audit was ranked differently from the thing it audited."""
        for resolver in (bp.resolve_bubble_position, bp.resolve_decision_valuation):
            source = inspect.getsource(resolver)
            self.assertIn("reference_readings(", source,
                          f"{resolver.__name__} builds its own pool")
            self.assertIn("local_date(now)", source,
                          f"{resolver.__name__} does not settle its window")

    # -- 3b. one clock, one tolerance -----------------------------------------

    def test_19_nothing_reads_the_machine_clock(self):
        """Everything stored is UTC. `datetime.now()` returns the runner's local
        time, so a filter written against it is correct only while the runner
        happens to be UTC -- which every CI runner is, and this workstation is not.
        `kpi_pre_sp_c2.test_13` proved it: a two-hour lookback reached back five and
        a half hours here and passed in CI."""
        # any read of the machine clock: datetime.now(), and datetime.now passed uncalled, as a
        # dataclass default -- two SignalState and HistoricalQuery stamps did that until 2026-10-16
        # (SP_D_HANDOFF.md section 37.3). datetime.now(timezone.utc) is UTC and allowed.
        clock = re.compile(r"datetime\.now\b(?!\(\s*timezone\.utc\s*\))")
        offenders = []
        for path in _python_files():
            if clock.search(_code(path)):
                offenders.append(path.name)
        self.assertEqual(sorted(offenders), [],
                         "use datetime.utcnow(); see timeutil for local dates")

    def test_20_shared_tolerances_are_defined_once(self):
        """0.05 existed as UNCHANGED_DEADBAND_PP, INCONCLUSIVE_DEADBAND_PP and
        BUBBLE_MOVEMENT_DEADBAND_PP across four modules, and 0.5 as
        COMPARABLE_BAND_FRACTION in two. Four names for one idea is four
        definitions that happen to agree."""
        import ast
        owners = {}
        for path in _python_files():
            try:
                tree = ast.parse(_read(path))
            except SyntaxError:
                continue
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if not isinstance(node.value, ast.Constant):
                    continue
                if not isinstance(node.value.value, (int, float)):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and (
                            "DEADBAND" in target.id or "BAND_FRACTION" in target.id):
                        owners.setdefault(target.id, []).append(path.name)
        self.assertEqual(
            {k: sorted(v) for k, v in owners.items()},
            {"UNCHANGED_DEADBAND_PP": ["tolerances.py"],
             "COMPARABLE_BAND_FRACTION": ["tolerances.py"]},
            "a shared tolerance is defined outside tolerances.py")
        from tolerances import UNCHANGED_DEADBAND_PP, COMPARABLE_BAND_FRACTION
        import analysis.decision_scorecard as ds
        import update.baseline_resolver as br
        self.assertIs(ds.INCONCLUSIVE_DEADBAND_PP, UNCHANGED_DEADBAND_PP)
        self.assertIs(br.BUBBLE_MOVEMENT_DEADBAND_PP, UNCHANGED_DEADBAND_PP)
        self.assertIs(ar.COMPARABLE_BAND_FRACTION, COMPARABLE_BAND_FRACTION)
        self.assertIs(bp.COMPARABLE_BAND_FRACTION, COMPARABLE_BAND_FRACTION)

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

    def test_26_the_structure_leg_is_a_rare_event_detector(self):
        """Registered, not fixed -- and the rare case must stay reachable.

        Across the whole discount range the leg returns one value, which is why it
        reads DISCOUNT_DOMINANT on 365 of 367 rows. That is not the same as useless:
        on the seven days it fires the other way the outcomes differ sharply
        (z = -2.04, against -0.98 / 0.07 / 1.40 for the three candidate
        replacements). Anyone simplifying this function must keep PREMIUM_DOMINANT
        and MIXED reachable.
        """
        if "structure_leg_fires_rarely" not in ACCEPTED:
            self.skipTest("entry retired")
        from caluclator.structure import evaluate_structure
        fair = 240_000_000

        def state(fractions):
            markets = {str(i): {"price": fair * (1 + f), "status": "OK"}
                       for i, f in enumerate(fractions)}
            return evaluate_structure(markets, fair)["state"]

        # Every discount, however deep, gives the same answer -- the constant.
        across = {state([-d / 100] * 5) for d in (0.8, 2.0, 3.5, 5.0, 8.0)}
        self.assertEqual(across, {"DISCOUNT_DOMINANT"},
                         "the leg now separates ordinary readings -- retire the "
                         "register entry and delete this test")

        # But the rare cases are still reachable, and they carry the signal.
        self.assertEqual(state([0.01] * 5), "PREMIUM_DOMINANT")
        self.assertEqual(state([-0.02, -0.02, 0.01, 0.01, 0.01]), "PREMIUM_DOMINANT")
        self.assertEqual(state([-0.02, -0.02, -0.02, 0.01, 0.01]), "DISCOUNT_DOMINANT")

    def test_27_no_kpi_reaches_the_live_network(self):
        """A KPI that fetches a live page is a network test wearing a unit test's
        name. It goes red when a site is slow, unreachable or geoblocked, and it
        cannot fail for the reason it was written -- a healthy network makes the
        error path unreachable.

        This has now happened twice in the same file. `kpi_pre_sp_c4.test_15` was
        de-networked earlier and carries a docstring about it; `test_13` beside it
        was still calling invi.ir and asserting status == "OK", and took the suite
        red mid-session. Both are substituted now.

        The rule: a KPI may name a collector entry point only if the same file also
        rebinds the transport it uses.

        Until 2026-10-16 this matched text that had no `name(` in it and passed on
        every file; it is read from the syntax tree now, and a sample offender below
        must be caught (SP_D_HANDOFF.md 37.8).
        """
        entry_points = {
            "get_invi_price": ("requests.get",),
            "get_world_gold_price": ("requests.get", "SOURCES"),
            "get_usd_sell_rate": ("subprocess.run",),
            "get_market_prices": ("COLLECTORS",),
            "fetch_feed": ("requests.get", "feedparser.parse"),
        }

        def offenders_in(source):
            calls, rebinds = _calls_and_rebinds(source)
            found = []
            for symbol, transports in entry_points.items():
                if symbol in calls and not any(
                        name == t or name.endswith("." + t) for name in rebinds for t in transports):
                    found.append(symbol)
            return found

        self.assertEqual(offenders_in("import collector.invi as invi\ninvi.get_invi_price()\n"),
                         ["get_invi_price"], "the check cannot see an unsubstituted call")
        self.assertEqual(offenders_in("import collector.invi as invi\n"
                                      "invi.requests.get, x = fake, 1\ninvi.get_invi_price()\n"), [])
        offenders, checked = [], 0
        for path in sorted(REPO.glob("kpi/*.py")):
            found = offenders_in(_read(path))
            checked += bool(_calls_and_rebinds(_read(path))[0] & set(entry_points))
            offenders += [f"{path.name}:{symbol}" for symbol in found]
        self.assertGreater(checked, 0, "no KPI calls a collector: the check has nothing to read")
        self.assertEqual(offenders, [],
                         "a KPI calls a collector without substituting its transport")

    def test_28_the_second_platform_is_judged_by_the_valuation_classifier(self):
        """The confirmation check ranks the second-cheapest platform, and it must say
        "heavily discounted" by exactly the rule the valuation leg uses: the one
        classifier, the one percentile helper, the one settled non-user pool. A
        second copy of any of the three is how `Deep discount` came to mean two
        numbers (SP_C_HANDOFF.md sections 24 and 38)."""
        # `_code` keeps one token per line, so a call is matched as its tokens.
        body = _code(SRC / "analysis" / "confirmation.py")
        for shared in ("classify_valuation", "_percentile_of", "reference_readings"):
            self.assertIn(f"{shared}\n(", body, f"confirmation no longer calls {shared}")
        for name in ("classify_valuation", "_percentile_of", "reference_readings"):
            self.assertNotIn(f"def\n{name}", body, f"confirmation defines its own {name}")
        for constant in ("CHEAP_PERCENTILE", "MIN_OBSERVATIONS", "DEFAULT_WINDOW_DAYS"):
            self.assertNotIn(f"\n{constant}\n=\n", body,
                             f"confirmation restates {constant} instead of importing it")

    def test_29_every_signal_passes_through_confirmation(self):
        """A BUY/SELL candidate reaches the final decision only through the
        confirmation check, and a BUY reaches the reader only through its own
        message. The first live BUY (2026-09-29) was sent on one stale quote because
        nothing stood between the candidate and the alert (SP_C_HANDOFF.md 37)."""
        body = _code(SRC / "main.py")
        self.assertIn("_resolve_signal_confirmation\n(", body)
        self.assertIn("confirmation\n=\nconfirmation", body,
                      "main builds the decision without its confirmation")
        self.assertIn("_send_buy_signal\n(", body,
                      "a BUY no longer reaches the reader through its own message")

    def test_33_the_model_and_the_schema_agree_that_a_news_link_is_text(self):
        """news_events.url was VARCHAR(500) in the model, the target schema and
        production, and Google News and percent-encoded Persian links are longer: 45
        items failed to save in six runs on 2026-09-30, each item lost entirely.
        Production was widened by sql/neon_migration_news_url.sql. The model and the
        target schema must say the same, or a rebuild reintroduces the limit
        (SP_C_HANDOFF.md section 40)."""
        from sqlalchemy import Text
        from database.models import NewsEvent
        column = NewsEvent.__table__.c.url.type
        self.assertIsInstance(column, Text, "the model limits news_events.url again")
        self.assertIsNone(getattr(column, "length", None))

        schema = (REPO / "sql" / "neon_schema.sql").read_text(encoding="utf-8")
        block = schema[schema.index("CREATE TABLE IF NOT EXISTS news_events"):]
        block = block[:block.index(");")]
        self.assertRegex(block, r"\burl TEXT\b", "the target schema limits news_events.url again")

        migration = (REPO / "sql" / "neon_migration_news_url.sql").read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE news_events ALTER COLUMN url TYPE TEXT", migration)

    def test_34_the_model_the_schema_and_the_migration_declare_one_candle_table(self):
        """market_daily_candles was created in production by
        sql/neon_migration_daily_candles.sql (SP_C_HANDOFF.md section 41.6). The model
        is what the code writes, the target schema is what a rebuild creates, and the
        migration is what production has. A column in one and not the others fails a
        write in production or disappears in a rebuild; an identity that differs lets
        the same trading day be stored twice."""
        from database.models import MarketDailyCandle
        table = MarketDailyCandle.__table__
        model_columns = {column.name for column in table.columns}
        identity = [c for c in table.constraints
                    if c.name == "uq_market_daily_candles_identity"]
        self.assertEqual(len(identity), 1, "the model lost its identity constraint")
        self.assertEqual([column.name for column in identity[0].columns],
                         ["source", "instrument", "trade_date"])

        sources = {
            "target schema": (REPO / "sql" / "neon_schema.sql").read_text(encoding="utf-8"),
            "migration": (REPO / "sql" / "neon_migration_daily_candles.sql").read_text(encoding="utf-8"),
        }
        for name, sql in sources.items():
            block = sql[sql.index("CREATE TABLE IF NOT EXISTS market_daily_candles"):]
            block = block[:block.index(");")]
            sql_columns = set(re.findall(r"^\s+([a-z_]+)\s+[A-Z]", block, re.MULTILINE))
            sql_columns.discard("CONSTRAINT")
            self.assertEqual(sql_columns, model_columns, f"the {name} and the model disagree")
            self.assertIn("CONSTRAINT uq_market_daily_candles_identity "
                          "UNIQUE (source, instrument, trade_date)", block,
                          f"the {name} has a different identity")

    def test_35_the_iran_node_table_is_one_table_and_its_role_only_inserts(self):
        """iran_node_readings was created in production by sql/neon_migration_iran_node.sql
        (SP_D_HANDOFF.md section 30). The node writes it through the role iran_node from a
        phone, so the role must be made by SQL and may only INSERT: a role made through
        Neon's API joins neon_superuser, which reads and writes every table."""
        from database.models import IranNodeReading
        model_columns = {column.name for column in IranNodeReading.__table__.columns}
        migration = (REPO / "sql" / "neon_migration_iran_node.sql").read_text(encoding="utf-8")
        sources = {"target schema": (REPO / "sql" / "neon_schema.sql").read_text(encoding="utf-8"),
                   "migration": migration}
        for name, sql in sources.items():
            block = sql[sql.index("CREATE TABLE IF NOT EXISTS iran_node_readings"):]
            block = block[:block.index(");")]
            sql_columns = set(re.findall(r"^\s+([a-z_]+)\s+[A-Z]", block, re.MULTILINE))
            self.assertEqual(sql_columns, model_columns, f"the {name} and the model disagree")
        self.assertIn("CREATE ROLE iran_node WITH LOGIN", migration)
        self.assertIn("GRANT INSERT ON iran_node_readings TO iran_node", migration)
        grants = re.findall(r"GRANT\s+(\w+)\s+ON\s+(?!SCHEMA|SEQUENCE)", migration)
        self.assertEqual(set(grants), {"INSERT"}, "the node's role may only insert")

    # -- 6. the register must stay honest -------------------------------------

    def test_36_no_hourly_reader_pulls_the_snapshots_json_it_does_not_read(self):
        """Neon's free plan suspended production on 2026-10-13 21:00 Tehran: 5.92 GB of outbound
        transfer against 5 GB a month (SP_D_HANDOFF.md section 34). Every hourly run read the last
        week's analysis snapshots whole -- six JSON documents a row -- to use an id, a timestamp, a
        regime or four prices: the outcome backfill twice over, the regime features up to 500 rows,
        the evidence package's outcome context. Each now loads only what it reads; the SQL they send
        must not name the documents."""
        from sqlalchemy import event
        from analysis import outcome_evaluator
        from database.models import AnalysisSnapshot
        from intelligence import features
        heavy = ("evidence_package_json", "features_json", "analysis_read_model_json",
                 "intelligence_result_json", "technical_state_json", "data_quality_json")
        session = _test_get_session()
        session.query(AnalysisSnapshot).delete()
        session.add(AnalysisSnapshot(analysis_timestamp=datetime.utcnow() - timedelta(hours=30),
                                     source_run_id="kpi-coherence-36", regime_state="NORMAL",
                                     xau_usd=4100, usd_irr=263000, rep_gold_price=262_000_000,
                                     premium_percent=-1.5, evidence_package_json={"big": "x" * 1000}))
        session.commit()
        session.close()
        sent = []
        listener = lambda conn, cursor, statement, params, context, many: sent.append(statement)
        event.listen(_TEST_ENGINE, "before_cursor_execute", listener)
        try:
            outcome_evaluator.backfill_outcome_evaluations(hours=168)
            features._build_regime_features("NORMAL", None, datetime.utcnow())
        finally:
            event.remove(_TEST_ENGINE, "before_cursor_execute", listener)
        reads = [s for s in sent if "FROM analysis_snapshots" in s]
        self.assertTrue(reads, "the readers ran against the snapshots")
        for statement in reads:
            for column in heavy:
                self.assertNotIn(column, statement, f"an hourly reader selects {column} again")
        from analysis import evidence_package
        self.assertIn('columns=("id", "analysis_timestamp")', inspect.getsource(evidence_package))
        session = _test_get_session()
        session.query(AnalysisSnapshot).delete()
        session.commit()
        session.close()

    def test_37_the_daily_candles_are_read_once_and_then_only_the_new_days(self):
        """The same week's second cut (SP_D_HANDOFF.md section 34): tgju's candles, about 26,000 rows
        a run, are kept between runs (persistence/candle_cache.py). Unchanged, a run reads none of
        them; a new day reads that day; a copy that disagrees is dropped and the instrument reread.
        Every read gives exactly what a direct read gives."""
        import tempfile
        from datetime import date as _date
        from sqlalchemy import event
        from database.models import MarketDailyCandle
        from persistence import candle_cache as cc
        from analysis import direction
        import main

        def add(day, close):
            s = _test_get_session()
            s.add(MarketDailyCandle(source="tgju", instrument="KPI37", trade_date=day, trade_date_jalali="",
                                    open=close, high=close + 1, low=close - 1, close=close, unit="IRR",
                                    source_quality="COMPLETE", collected_at=datetime(2026, 10, 15)))
            s.commit()
            s.close()

        def read():
            sent.clear()
            s = _test_get_session()
            try:
                return [(r.trade_date, r.open, r.high, r.low, r.close, r.source_quality)
                        for r in cc.candles(s, "tgju", "KPI37")]
            finally:
                s.close()

        def direct():
            os.environ.pop("CANDLE_CACHE_FILE", None)
            try:
                return read()
            finally:
                os.environ["CANDLE_CACHE_FILE"] = path

        for k in range(5):
            add(_date(2026, 10, 1) + timedelta(days=k), 100.0 + k)
        path = os.path.join(tempfile.mkdtemp(), "candle_cache.json")
        os.environ["CANDLE_CACHE_FILE"] = path
        sent = []
        listener = lambda conn, cursor, statement, params, context, many: sent.append(statement)
        event.listen(_TEST_ENGINE, "before_cursor_execute", listener)
        rows_read = lambda: [s for s in sent if "market_daily_candles.open" in s]
        try:
            first = read()
            self.assertEqual(first, direct())
            self.assertTrue(os.path.exists(path), "the copy is written")
            second = read()
            self.assertEqual(second, first)
            self.assertEqual(rows_read(), [], "an unchanged instrument reads no candle rows")
            add(_date(2026, 10, 6), 110.0)
            third = read()
            third_reads = rows_read()
            self.assertEqual(third, direct())
            self.assertEqual(len(third_reads), 1)
            self.assertIn("trade_date >", third_reads[0], "only the days after the copy's")
            s = _test_get_session()
            s.query(MarketDailyCandle).filter(MarketDailyCandle.instrument == "KPI37",
                                              MarketDailyCandle.trade_date == _date(2026, 10, 2)).delete()
            s.commit()
            s.close()
            fourth = read()
            self.assertEqual(fourth, direct(), "a copy that disagrees is dropped and the instrument reread")
        finally:
            event.remove(_TEST_ENGINE, "before_cursor_execute", listener)
            os.environ.pop("CANDLE_CACHE_FILE", None)
            s = _test_get_session()
            s.query(MarketDailyCandle).filter(MarketDailyCandle.instrument == "KPI37").delete()
            s.commit()
            s.close()
        self.assertIn('candles(session, "tgju", instrument)', inspect.getsource(direction.load_series))
        self.assertIn('candles(session, "tgju", GOLD)', inspect.getsource(main._room_state))
        workflow = (REPO / ".github" / "workflows" / "gold-monitor.yml").read_text(encoding="utf-8")
        self.assertIn("candle_cache.json", workflow.split("Cache pip packages")[0], "kept with state.json")
        self.assertIn("CANDLE_CACHE_FILE: candle_cache.json", workflow)

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


    # -- the spool (SP_D_HANDOFF.md section 35.4) ------------------------------------------

    def _spool_file(self):
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "record_spool.jsonl")
        os.environ["RECORD_SPOOL_FILE"] = path
        self.addCleanup(os.environ.pop, "RECORD_SPOOL_FILE", None)
        return path

    @staticmethod
    def _quota_error():
        from sqlalchemy.exc import OperationalError
        return OperationalError("INSERT", {}, Exception("Your project has exceeded the data transfer quota"))

    def test_38_what_the_database_cannot_take_is_held_and_written_back_once(self):
        """Neon refused every connection from 2026-10-13 21:00 to the month's end, and each run's reading,
        observations and the room's inputs were lost. Held instead, they are written back by the next run
        that reaches the database, with their original times, and never twice."""
        import io
        from contextlib import redirect_stdout
        from datetime import date as _date
        from caluclator.signal_state import SignalState
        from collector import tablokhani
        from database import repository as repo
        from database.models import MarketDailyCandle, MarketState, PriceObservation
        from persistence import spool
        import main

        path = self._spool_file()
        when = datetime(2026, 10, 14, 10, 30, 17, 123456)
        state = SignalState(premium=-1.74, fair_price=FAIR, lowest_price=FAIR * 0.98, valuation="UNKNOWN",
                            final_decision="WAIT", reason="held: no rank", timestamp=when)
        prices = [{"platform_name": "Milli", "price_irr": FAIR * 0.98, "change_irr": None},
                  {"platform_name": "Goldika", "price_irr": FAIR * 1.01, "change_irr": None}]
        self.assertTrue(main._hold_reading(when, FAIR, -1.74, 4157.0, 266_800.0, state, prices, "scheduled"))

        class Down:  # a session whose every write fails as Neon's did
            def __init__(self, error):
                self.error = error
            def add(self, _):
                pass
            def commit(self):
                raise self.error
            def rollback(self):
                pass
            def close(self):
                pass

        from sqlalchemy.exc import IntegrityError
        real_session, real_save, real_collect = repo.get_session, repo.save_daily_candles, tablokhani.collect
        try:
            with redirect_stdout(io.StringIO()):
                repo.get_session = lambda: Down(self._quota_error())
                self.assertEqual(repo.save_price_observation("USD/IRR", "bonbast", when, 266_800.0, "FRESH", "run-1",
                                                             "SINGLE", "scheduled"), -1)
                repo.get_session = lambda: Down(IntegrityError("INSERT", {}, Exception("a rejected row")))
                repo.save_price_observation("USD/IRR", "bonbast", when, 1.0, "FRESH", "run-1", "SINGLE", "scheduled")
                repo.get_session = real_session

                def refused(*args, **kwargs):
                    raise self._quota_error()
                repo.save_daily_candles = refused
                tablokhani.collect = lambda: {"afran_close": 55_210.0, "tedpix": 3_150_000.0, "tse_state": "closed",
                                              "afran": None, "funds": {}, "errors": []}
                main._collect_room_inputs(datetime(2026, 10, 14, 11, 0))      # 14:30 Tehran: no etfbaz yet
                main._collect_room_inputs(datetime(2026, 10, 14, 12, 0))      # the next run: already held today
        finally:
            repo.get_session, repo.save_daily_candles, tablokhani.collect = real_session, real_save, real_collect

        entries = spool.held()
        self.assertEqual([e["kind"] for e in entries], ["reading", "observation", "candles", "candles"],
                         "an unreachable database is held; a row it rejects is not")
        self.assertEqual(entries[0]["payload"]["snapshot"]["timestamp"], when, "times come back as they were")

        s = _test_get_session()
        try:
            written = spool.flush(s, repo.spool_writers(s, entries), entries)
        finally:
            s.close()
        self.assertEqual(written, (4, 0, 0))
        self.assertFalse(os.path.exists(path), "a written spool is removed")
        s = _test_get_session()
        try:
            snaps = s.query(MarketSnapshot).filter(MarketSnapshot.timestamp == when).all()
            self.assertEqual([(x.collection_mode, round(float(x.premium_percent), 2)) for x in snaps], [("scheduled", -1.74)])
            self.assertEqual(sorted(p.platform_name for p in s.query(PlatformPrice).filter(PlatformPrice.snapshot_id == snaps[0].id)),
                             ["Goldika", "Milli"])
            st = s.query(MarketState).filter(MarketState.snapshot_id == snaps[0].id).one()
            self.assertEqual((st.final_decision, st.valuation_state, st.timestamp), ("WAIT", "UNKNOWN", when))
            self.assertEqual(s.query(PriceObservation).filter(PriceObservation.timestamp == when).count(), 1)
            days = {r.instrument: float(r.close) for r in s.query(MarketDailyCandle).filter(
                MarketDailyCandle.trade_date == _date(2026, 10, 14), MarketDailyCandle.instrument.in_(["AFRAN_LAST", "TSE_TEDPIX"]))}
            self.assertEqual(days, {"AFRAN_LAST": 55_210.0, "TSE_TEDPIX": 3_150_000.0})
        finally:
            s.close()

        # a flush that stored its writes but ended before the file was rewritten: held again, stored once
        for e in entries:
            spool.hold(e["kind"], e["payload"])
        s = _test_get_session()
        try:
            again = spool.held()
            spool.flush(s, repo.spool_writers(s, again), again)
            self.assertEqual(s.query(MarketSnapshot).filter(MarketSnapshot.timestamp == when).count(), 1)
            self.assertEqual(s.query(PriceObservation).filter(PriceObservation.timestamp == when).count(), 1)
            self.assertEqual(s.query(MarketDailyCandle).filter(MarketDailyCandle.trade_date == _date(2026, 10, 14),
                                                              MarketDailyCandle.instrument == "AFRAN_LAST").count(), 1)
        finally:
            s.close()

    def test_39_an_unreachable_database_stops_the_flush_and_a_rejected_write_is_dropped(self):
        from persistence import spool
        path = self._spool_file()

        class Book:  # a session that keeps what was committed
            def __init__(self):
                self.pending, self.stored = [], []
            def commit(self):
                self.stored += self.pending
                self.pending = []
            def rollback(self):
                self.pending = []

        def write(session, payload):
            if payload == "rejected":
                raise ValueError("a row the database rejects")
            if payload == "down":
                raise self._quota_error()
            session.pending.append(payload)

        def run(payloads, clock=None):
            if os.path.exists(path):
                os.remove(path)
            for p in payloads:
                spool.hold("observation", p)
            book = Book()
            entries = spool.held()
            out = (spool.flush(book, {"observation": write}, entries, clock=clock) if clock
                   else spool.flush(book, {"observation": write}, entries))
            return out, book.stored, [e["payload"] for e in spool.held()]

        self.assertEqual(run(["a", "rejected", "b"]), ((2, 1, 0), ["a", "b"], []),
                         "a rejected batch is retried one by one and only the rejected write dropped")
        self.assertEqual(run(["a", "down", "b"]), ((0, 0, 3), [], ["a", "down", "b"]),
                         "an unreachable database keeps everything not written")
        many = [f"o{k}" for k in range(spool.BATCH + 5)]
        ticks = iter([0, 0, spool.FLUSH_SECONDS + 1])
        out, stored, left = run(many, clock=lambda: next(ticks))
        self.assertEqual((out, stored, left), ((spool.BATCH, 0, 5), many[:spool.BATCH], many[spool.BATCH:]),
                         "a run writes for a bounded time; the rest wait for the next")

    def test_40_the_spool_is_wired_where_the_record_is_written(self):
        import inspect
        import main
        run = inspect.getsource(main.main)
        self.assertIn("if is_scheduled:\n        _flush_spool(config)", run, "write-back on scheduled runs, not on a reader's Update")
        self.assertLess(run.index("_flush_spool(config)"), run.index("now = datetime.utcnow()"),
                        "before the run takes its time: a write-back can last minutes")
        self.assertLess(run.index("_flush_spool(config)"), run.index("_recent_platform_history("),
                        "before the stale-quote check reads the platform history")
        self.assertIn("if unreachable(e) and _hold_reading(", run)
        flush = inspect.getsource(main._flush_spool)
        self.assertLess(flush.index("_recheck_held("), flush.index("spool.flush("),
                        "held readings meet the stale-quote rules before anything is written (section 37.1)")
        workflow = (REPO / ".github" / "workflows" / "gold-monitor.yml").read_text(encoding="utf-8")
        self.assertIn("RECORD_SPOOL_FILE: record_spool.jsonl", workflow)
        self.assertIn("            record_spool.jsonl\n", workflow.replace("\r\n", "\n"), "kept in the cache between runs")


    def test_41_held_readings_meet_the_stale_quote_rules_before_they_are_written(self):
        """Readings held while Neon was down skipped the repeat and jump rules, which need the stored
        history (SP_D_HANDOFF.md sections 35.12, 37.1). At the write-back each is judged as its run would
        have been, so a frozen copy held during the outage never reaches the database."""
        import io
        from contextlib import redirect_stdout
        import main

        s = _test_get_session()
        start = datetime(2026, 9, 20, 6, 0)
        offsets = {"WallGold": 1.000, "Milli": 0.992, "Goldika": 1.010, "Ayyareh": 0.998}
        frozen = None
        try:
            for k in range(15 * 12):                                   # 15 days, every 2 hours
                ts = start + timedelta(hours=2 * k)
                base = 250_000_000 * (1 + 0.0004 * k)
                snap = MarketSnapshot(collection_mode="scheduled", timestamp=ts, fair_price=base * 1.03,
                                      premium_percent=-3.0)
                s.add(snap)
                s.flush()
                for name, off in offsets.items():
                    s.add(PlatformPrice(snapshot_id=snap.id, platform_name=name, price_irr=base * off, timestamp=ts))
                if k == 100:
                    frozen = base * offsets["Ayyareh"]                 # what Ayyareh's copy will repeat
            s.commit()
            last_base = 250_000_000 * (1 + 0.0004 * 179)
            held, observations = [], []
            for h in range(2):
                ts = start + timedelta(hours=2 * 180 + h)
                moved = last_base * 1.04
                prices = {name: moved * off for name, off in offsets.items()}
                prices["Ayyareh"] = frozen                              # a copy from days ago, far below the rest
                fair = moved * 1.03
                held.append({"kind": "reading", "payload": {
                    "snapshot": {"timestamp": ts, "fair_price": fair, "premium_percent": (frozen / fair - 1) * 100,
                                 "world_gold_usd": 4100.0, "usd_irr": 2_650_000.0, "signal": "WAIT",
                                 "confidence": None, "collection_mode": "scheduled"},
                    "platform_prices": [{"platform_name": n, "price_irr": p, "change_irr": None} for n, p in prices.items()],
                    "state": {"platform_low": frozen, "structure_state": "DISCOUNT_DOMINANT", "final_decision": "WAIT"}}})
                for n, p in prices.items():
                    observations.append({"kind": "observation", "payload": {
                        "instrument": "REP_IRAN_GOLD", "source": n.lower(), "timestamp": ts, "price": p}})
            with redirect_stdout(io.StringIO()) as out:
                kept, deferred = main._recheck_held(s, held + observations)
        finally:
            s.rollback()
            s.close()
        self.assertEqual(deferred, 2, "the frozen copy, in both held readings")
        self.assertIn("deferred Ayyareh", out.getvalue())
        readings = [e["payload"] for e in kept if e["kind"] == "reading"]
        self.assertEqual(len(readings), 2)
        for r in readings:
            names = {pp["platform_name"] for pp in r["platform_prices"]}
            self.assertEqual(names, {"WallGold", "Milli", "Goldika"})
            low = min(pp["price_irr"] for pp in r["platform_prices"])
            self.assertAlmostEqual(r["snapshot"]["premium_percent"], (low / r["snapshot"]["fair_price"] - 1) * 100)
            self.assertAlmostEqual(r["state"]["platform_low"], low, msg="the state's platform fields follow")
        sources = {(e["payload"]["source"]) for e in kept if e["kind"] == "observation"}
        self.assertEqual(sources, {"wallgold", "milli", "goldika"}, "its observations leave with it")

    def test_42_a_held_reading_left_without_enough_platforms_is_dropped(self):
        import io
        from contextlib import redirect_stdout
        import main
        from validation import data as v

        real = v.MIN_WORKING_SOURCES
        held = [{"kind": "reading", "payload": {
            "snapshot": {"timestamp": datetime(2026, 10, 20, 8), "fair_price": 100.0, "premium_percent": -3.0,
                         "collection_mode": "scheduled"},
            "platform_prices": [{"platform_name": "A", "price_irr": 97.0}, {"platform_name": "B", "price_irr": 96.0}]}},
            {"kind": "observation", "payload": {"instrument": "XAUUSD", "source": "kitco",
                                                "timestamp": datetime(2026, 10, 20, 8), "price": 4100.0}}]
        import database.repository as repo
        real_history, real_defer = repo.get_recent_platform_prices, v.defer_stale_quotes

        def defer(valid, history, now, holds=None):
            valid.pop("B")
            return [("B", "a copy")]
        try:
            repo.get_recent_platform_prices = lambda session, since: []
            v.defer_stale_quotes = defer
            with redirect_stdout(io.StringIO()):
                kept, deferred = main._recheck_held(None, held)
        finally:
            repo.get_recent_platform_prices, v.defer_stale_quotes = real_history, real_defer
        self.assertEqual(real, v.MIN_WORKING_SOURCES)
        self.assertEqual((kept, deferred), ([], 1), "fewer than the minimum: the run would have skipped it, and so do we")


    def test_43_the_analysis_wing_parts_nothing_reads_are_parked_by_config(self):
        """Owner 2026-10-16: the wing is to be rethought, not retired. Meanwhile the interpretation chain,
        the C.14A candles and the C.14B forecasts -- read by nothing a reader sees or the decision uses,
        about 80% of each run -- are parked by config.json; the snapshot's core and the outcome
        evaluations, which the scorecard needs, run (SP_D_HANDOFF.md section 37.2)."""
        import inspect as _inspect
        from analysis import snapshot_builder as sb
        cfg = json.loads((REPO / "config" / "config.json").read_text(encoding="utf-8"))
        wing = cfg["analysis_wing"]
        self.assertEqual((wing["interpretation"], wing["candles"], wing["forecasts"]), (False, False, False))
        self.assertIn("section 37.2", wing["parked_2026_10_16"])
        src = _inspect.getsource(sb.build_analysis_snapshot)
        self.assertIn('wing.get("candles", True)', src, "absent, everything runs as before")
        self.assertIn('wing.get("forecasts", True)', src)
        self.assertIn('wing.get("interpretation", True)', src)
        self.assertNotIn("_Parked", src[src.index("run_outcome_evaluation_for_snapshot"):src.index("backfill_outcome_evaluations")],
                         "the outcome evaluations are never parked")

    def test_44_analyze_says_the_database_is_out_of_reach(self):
        import io
        from contextlib import redirect_stdout
        import main
        import alerts.telegram as tg
        sent, saved = [], (main._database_reachable, tg._send)
        try:
            main._database_reachable = lambda: False
            tg._send = sent.append
            with redirect_stdout(io.StringIO()):
                main._send_analyze_report()
        finally:
            main._database_reachable, tg._send = saved
        self.assertEqual(len(sent), 1)
        self.assertIn("out of reach", sent[0])
        self.assertNotIn("Not enough history", sent[0], "the history was never the problem")


    def test_45_two_sided_platforms_store_both_sides_and_the_representative_chain_keeps_one(self):
        """Both price sides where a platform publishes them (owner 2026-10-16: "collecting both sides is better";
        SP_D_HANDOFF.md section 37.7). Ayyareh stays one row: the representative chain reads its latest
        observation without a side."""
        import io
        from contextlib import redirect_stdout
        import main
        from analysis.representative_price import FALLBACK_CHAIN
        calls, real = [], main.save_price_observation
        main.save_price_observation = lambda **k: calls.append((k["source"], k["quote_side"], k["price"])) or 1
        markets = {name: {"status": "OK", "price": 100.0, "buy": 101.0, "sell": 99.0}
                   for name in ("Goldika", "Daric", "Taline", "Ayyareh")}
        markets["Milli"] = {"status": "OK", "price": 98.0}
        try:
            with redirect_stdout(io.StringIO()):
                main._save_price_observations(markets, None, None, datetime(2026, 10, 16, 8), 15, "run")
        finally:
            main.save_price_observation = real
        sides = {}
        for source, side, price in calls:
            sides.setdefault(source, set()).add(side)
        for name in main.TWO_SIDED_OBSERVED:
            self.assertEqual(sides[name.lower()], {"BUY", "SELL"}, name)
        self.assertEqual(sides["ayyareh"], {"SINGLE"})
        self.assertEqual(sides["milli"], {"SINGLE"})
        self.assertFalse({n.lower() for n in main.TWO_SIDED_OBSERVED} & set(FALLBACK_CHAIN),
                         "no platform of the representative chain is stored two-sided")

    def test_46_taline_reads_its_two_sides(self):
        from collector.taline import sides
        page = "قیمت خرید طلا: ۲۶,۲۹۴,۷۰۰ قیمت فروش طلا: ۲۶,۰۸۵,۲۰۰ تومان"
        self.assertEqual(sides(page), {"buy": 262_947_000.0, "sell": 260_852_000.0}, "Persian digits, toman to rial")
        self.assertEqual(sides("قیمت خرید طلا: ۲۶,۰۰۰ قیمت فروش طلا: ۲۷,۰۰۰"), {}, "a sell above the buy is not trusted")
        self.assertEqual(sides("no prices here"), {})


    # -- the record mirror (SP_D_HANDOFF.md section 37.12) ------------------------------

    def _mirror_file(self, reachable):
        """A copy in a temporary file, with Neon's reachability fixed for the test."""
        import tempfile
        from persistence import mirror
        path = os.path.join(tempfile.mkdtemp(), "record_mirror.sqlite")
        os.environ["RECORD_MIRROR_FILE"] = path
        mirror._engine, mirror._reachable = None, reachable

        def reset():
            os.environ.pop("RECORD_MIRROR_FILE", None)
            if mirror._engine is not None:
                mirror._engine.dispose()
            mirror._engine, mirror._reachable = None, None
        self.addCleanup(reset)
        return mirror

    @staticmethod
    def _seventy_days():
        """Six readings a day for 70 days, sized like production's record."""
        start = NOW - timedelta(days=70)
        return [(start + timedelta(hours=4 * i), "scheduled", PRODUCTION_SHAPE[i % len(PRODUCTION_SHAPE)])
                for i in range(70 * 6)]

    def test_47_the_mirror_copies_sixty_days_then_only_what_is_new(self):
        """A scheduled run that reaches Neon copies the last 61 days of readings and their platform
        prices; the next copies only the readings added since; a week later it copies everything
        again, which is how a row corrected in place reaches the copy."""
        from sqlalchemy import func, select
        mirror = self._mirror_file(reachable=True)
        _seed(self._seventy_days())
        source = _test_get_session()
        try:
            copied = mirror.refresh(source, NOW)
            window = source.query(MarketSnapshot).filter(
                MarketSnapshot.timestamp >= NOW - timedelta(days=mirror.WINDOW_DAYS)).count()
            self.assertEqual(copied, window * 5, "each reading and its four platform prices")
            with mirror._mirror_engine().connect() as m:
                snap = MarketSnapshot.__table__
                self.assertEqual(m.execute(select(func.count()).select_from(snap)).scalar(), window)
                oldest = m.execute(select(func.min(snap.c.timestamp))).scalar()
            self.assertGreaterEqual(oldest, NOW - timedelta(days=mirror.WINDOW_DAYS), "nothing older than the window")

            later = NOW + timedelta(hours=1)
            added = MarketSnapshot(timestamp=later, world_gold_usd=4300.0, usd_irr=230_000.0,
                                   fair_price=FAIR, premium_percent=-3.0, collection_mode="scheduled")
            source.add(added)
            source.flush()
            source.add(PlatformPrice(snapshot_id=added.id, platform_name="A", timestamp=later,
                                     price_irr=FAIR * 0.97))
            first = source.query(MarketSnapshot).order_by(MarketSnapshot.timestamp.desc()).offset(5).first()
            first.premium_percent = -9.99          # a correction made in place, as section 45's were
            source.commit()
            self.assertEqual(mirror.refresh(source, later), 2, "only the new reading and its price")
            with mirror._mirror_engine().connect() as m:
                kept = m.execute(select(snap.c.premium_percent).where(snap.c.id == first.id)).scalar()
            self.assertNotAlmostEqual(float(kept), -9.99, msg="an in-place correction waits for the weekly copy")

            week = NOW + timedelta(days=mirror.REBUILD_DAYS, hours=2)
            mirror.refresh(source, week)
            with mirror._mirror_engine().connect() as m:
                kept = m.execute(select(snap.c.premium_percent).where(snap.c.id == first.id)).scalar()
            self.assertAlmostEqual(float(kept), -9.99, msg="the weekly copy carries it")
            self.assertEqual(mirror.built_at(), week)
        finally:
            source.close()

    def test_48_reads_come_from_the_copy_only_when_neon_is_out_of_reach_and_answer_the_same(self):
        """Out of reach, the valuation rank, the platform history and UPDATE's readers get the copy,
        and it gives the answers Neon gives. In reach, or unset, they get Neon as before. The copy
        refuses to write."""
        import main
        from database.repository import get_recent_platform_prices
        from analysis.bubble_position import resolve_decision_valuation
        mirror = self._mirror_file(reachable=True)
        _seed(self._seventy_days())
        source = _test_get_session()
        mirror.refresh(source, NOW)
        thresholds = _config()["thresholds"]
        since = NOW - timedelta(days=60)

        neon = main._read_session()
        self.assertIs(neon.bind, _TEST_ENGINE, "Neon in reach: Neon")
        neon.close()

        mirror._reachable = False
        copy = main._read_session()
        try:
            self.assertIsNot(copy.bind, _TEST_ENGINE, "Neon out of reach: the copy")
            self.assertEqual([(t, n, float(p)) for _, t, n, p in get_recent_platform_prices(copy, since)],
                             [(t, n, float(p)) for _, t, n, p in get_recent_platform_prices(source, since)],
                             "the stale-quote rules see the same history")
            on_neon = resolve_decision_valuation(source, -4.2, thresholds, now=NOW)
            on_copy = resolve_decision_valuation(copy, -4.2, thresholds, now=NOW)
            self.assertEqual((on_copy.state, on_copy.percentile, on_copy.sample_size),
                             (on_neon.state, on_neon.percentile, on_neon.sample_size),
                             "the valuation leg ranks the same reading the same way")
            self.assertNotEqual(on_copy.state, "UNKNOWN", "and it has a rank to give")
            copy.add(MarketSnapshot(timestamp=NOW, fair_price=FAIR, premium_percent=-1.0, collection_mode="user"))
            with self.assertRaises(RuntimeError):
                copy.commit()
        finally:
            copy.close()
            source.close()

        os.environ.pop("RECORD_MIRROR_FILE")
        unset = main._read_session()
        self.assertIs(unset.bind, _TEST_ENGINE, "unset: Neon, as before")
        unset.close()

    def test_49_a_held_reading_reaches_the_next_runs_reads_and_the_rebuild_drops_it(self):
        """A reading the spool holds is added to the copy under a negative id, so the stale-quote rules
        and the rank of the next run see it. When Neon answers again the copy is rebuilt from Neon,
        where the spool has written it, and the negative ids go. Without a copy made from Neon nothing
        is added: a copy of the outage alone would rank a reading against a few hours."""
        import io
        from contextlib import redirect_stdout
        from sqlalchemy import func, select
        from caluclator.signal_state import SignalState
        from database.repository import get_recent_platform_prices
        import main

        self._spool_file()
        mirror = self._mirror_file(reachable=False)
        when = NOW + timedelta(hours=3)
        state = SignalState(premium=-3.1, fair_price=FAIR, lowest_price=FAIR * 0.969, valuation="FAIR",
                            final_decision="WAIT", reason="held", timestamp=when)
        prices = [{"platform_name": "A", "price_irr": FAIR * 0.969, "change_irr": None},
                  {"platform_name": "B", "price_irr": FAIR * 0.975, "change_irr": None}]
        self.assertTrue(main._hold_reading(when, FAIR, -3.1, 4300.0, 230_000.0, state, prices, "scheduled"))
        self.assertIsNone(mirror.built_at())
        with mirror._mirror_engine().connect() as m:
            self.assertEqual(m.execute(select(func.count()).select_from(MarketSnapshot.__table__)).scalar(), 0,
                             "no copy from Neon: nothing added")

        _seed(self._seventy_days())
        source = _test_get_session()
        mirror._reachable = True
        mirror.refresh(source, NOW)
        mirror._reachable = False
        self.assertTrue(main._hold_reading(when, FAIR, -3.1, 4300.0, 230_000.0, state, prices, "scheduled"))
        copy = main._read_session()
        try:
            rows = get_recent_platform_prices(copy, NOW)
            self.assertEqual(sorted((n, round(float(p))) for sid, t, n, p in rows if sid < 0),
                             sorted((r["platform_name"], round(r["price_irr"])) for r in prices),
                             "the held reading is in the next run's history")
        finally:
            copy.close()

        mirror._reachable = True
        with redirect_stdout(io.StringIO()):
            mirror.refresh(source, when + timedelta(hours=1))
        with mirror._mirror_engine().connect() as m:
            snap = MarketSnapshot.__table__
            self.assertEqual(m.execute(select(func.count()).select_from(snap).where(snap.c.id < 0)).scalar(), 0,
                             "rebuilt from Neon once it answers")
        source.close()

    def test_50_only_the_reads_the_copy_can_answer_use_it(self):
        """The copy holds two tables, so only their readers ask for it. The deep-discount push stays as the
        owner parked it during an outage; PAPER, ANALYZE and Direction do not read the copy; every writer
        keeps Neon's session and the spool."""
        import main
        from update import baseline_resolver
        readers = {"_resolve_decision_valuation", "_recent_platform_history", "_resolve_signal_confirmation",
                   "_resolve_presentation_context", "main"}
        for name in readers:
            self.assertIn("_read_session()", inspect.getsource(getattr(main, name)), name)
        for name in ("_evaluate_deep_discount_push", "_paper_run", "_send_analyze_report", "_direction_precompute",
                     "_send_direction_report", "_flush_spool", "_save_price_observations", "_collect_tgju_candles"):
            self.assertNotIn("_read_session()", inspect.getsource(getattr(main, name)), name)
        self.assertIn("read_session()", inspect.getsource(baseline_resolver.resolve_update_baselines))
        self.assertIn("_refresh_mirror(now)", inspect.getsource(main.main))
        workflow = (REPO / ".github" / "workflows" / "gold-monitor.yml").read_text(encoding="utf-8")
        self.assertIn("path: record_mirror.sqlite\n          key: gold-monitor-mirror-", workflow.replace("\r\n", "\n"),
                      "cached in its own entry")
        self.assertIn("RECORD_MIRROR_FILE: record_mirror.sqlite", workflow)

    def test_52_the_state_cache_keeps_its_list_of_files(self):
        """A cache entry belongs to its exact list of paths. Adding record_mirror.sqlite to the state's
        list made every earlier entry invisible: the run of 2026-10-16 12:30 UTC started from an empty
        state.json and spool, and the readings held since 10-15 were out of reach (SP_D_HANDOFF.md section
        37.14). The list is fixed; a new file gets its own cache step."""
        import re as _re
        workflow = (REPO / ".github" / "workflows" / "gold-monitor.yml").read_text(encoding="utf-8").replace("\r\n", "\n")
        step = workflow.split("- name: Restore State\n", 1)[1].split("\n      - name:", 1)[0]
        paths = _re.search(r"path: \|\n((?:            \S+\n)+)", step).group(1).split()
        self.assertEqual(paths, ["state.json", "candle_cache.json", "record_spool.jsonl"])
        self.assertIn("key: gold-monitor-state-${{ github.run_id }}", step)

    def test_51_news_is_held_once_while_the_database_is_out_of_reach_and_written_back_once(self):
        """The feeds keep only their latest items, so news a run cannot store is lost (SP_D_HANDOFF.md
        section 37.11); the owner, 2026-10-16: "spool". A save that finds Neon out of reach holds the
        item; its key keeps the next runs from holding it again; the write-back stores it once, with its
        own time, and skips an item already stored. News stops at its own ceiling, which leaves the rest
        of the spool to the record."""
        import io
        from contextlib import redirect_stdout
        from database import repository as repo
        from database.models import NewsEvent
        from persistence import spool

        self._spool_file()
        published = datetime(2026, 10, 16, 12, 25, 20)
        item = {"published_at": published, "source": "tasnimnews.ir/feeds/7", "url": "https://www.tasnimnews.ir/a",
                "dedup_key": "kpi51-a", "title": "a held headline", "summary": "s", "event_type": "UNKNOWN",
                "relevance": "UNKNOWN", "classification_method": "KEYWORD"}

        class Down:
            def __init__(self, error):
                self.error = error
            def add(self, _):
                pass
            def commit(self):
                raise self.error
            def rollback(self):
                pass
            def close(self):
                pass

        real = repo.get_session
        try:
            repo.get_session = lambda: Down(self._quota_error())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(repo.save_news_event(item), 0, "held, not failed")
        finally:
            repo.get_session = real
        self.assertEqual(spool.held_keys("news", "dedup_key"), {"kpi51-a"})

        s = _test_get_session()
        try:
            s.query(NewsEvent).filter(NewsEvent.dedup_key.like("kpi51-%")).delete(synchronize_session=False)
            s.add(NewsEvent(timestamp=published, source="x", dedup_key="kpi51-b", raw_headline="already stored",
                            event_type="UNKNOWN", relevance="UNKNOWN", classification_method="KEYWORD",
                            processed_at=published))
            s.commit()
            self.assertTrue(repo.hold_news_event({**item, "dedup_key": "kpi51-b", "title": "stored before"}))
            entries = spool.held()
            with redirect_stdout(io.StringIO()):
                written, dropped, left = spool.flush(s, repo.spool_writers(s, entries), entries)
            self.assertEqual((written, dropped, left), (2, 0, 0))
            rows = s.query(NewsEvent).filter(NewsEvent.dedup_key.like("kpi51-%")).all()
            self.assertEqual(sorted(r.dedup_key for r in rows), ["kpi51-a", "kpi51-b"], "each once")
            held_row = [r for r in rows if r.dedup_key == "kpi51-a"][0]
            self.assertEqual((held_row.timestamp, held_row.source), (published, "tasnimnews.ir/feeds/7"))
            s.query(NewsEvent).filter(NewsEvent.dedup_key.like("kpi51-%")).delete(synchronize_session=False)
            s.commit()
        finally:
            s.close()

        ceiling = spool.NEWS_MAX_BYTES
        try:
            spool.NEWS_MAX_BYTES = 10
            self.assertTrue(spool.hold("observation", {"timestamp": published}), "the record still fits")
            self.assertFalse(repo.hold_news_event(item), "news stops at its own ceiling")
        finally:
            spool.NEWS_MAX_BYTES = ceiling


    # -- the SERVICE notice (SP_D_HANDOFF.md section 37.15) ------------------------------

    def test_53_a_service_change_is_announced_once_after_two_runs(self):
        """Every run of the October outage finished green, so Telegram's Status said all was well (the
        owner: "the user should be informed of any possible outage"). A change is announced once two
        scheduled runs agree, dated from the first; an outage under way is dated by the spool's oldest
        held write; the reader is told what still works, what waits, and when Neon's allowance returns."""
        from analysis import service
        from alerts.telegram_service import build_message, status_line
        quota = "Your project has exceeded the data transfer quota. Upgrade your plan to increase limits."
        markets = {f"P{k}": {"status": "OK"} for k in range(9)}
        held_since = datetime(2026, 10, 13, 17, 30)                       # 21:00 Tehran
        t = [datetime(2026, 10, 16, 12, 30) + timedelta(hours=k) for k in range(6)]
        state = {}

        def run(when, db_ok, world_ok=True):
            seen = service.observe(4150.0 if world_ok else 4150.0, not world_ok, 270_000.0, markets, db_ok,
                                   "" if db_ok else quota, None if db_ok else held_since)
            return service.update(state, seen, when)

        self.assertEqual(run(t[0], False), [], "one run is not enough")
        changes = run(t[1], False)
        self.assertEqual([(n, c) for n, c, _ in changes], [("database", "down")])
        self.assertEqual(changes[0][2]["since"], held_since.isoformat(), "dated by the oldest held write")
        self.assertEqual(run(t[2], False), [], "announced once")
        self.assertEqual(run(t[3], True), [])
        back = run(t[4], True)
        self.assertEqual([(n, c) for n, c, _ in back], [("database", "back")])

        down_text = build_message("database", "down", changes[0][2], t[1])
        self.assertIn("The database is out of reach since 21 Mehr, 21:00 (its free monthly limit).", down_text)
        self.assertIn("Working: UPDATE, DIRECTION, the 21:00 chart.", down_text)
        self.assertIn("Paused: ANALYZE, the discount push, the room's report, BUY signals.", down_text)
        self.assertIn("Expected back: 10 Aban.", down_text)
        self.assertNotIn("BUY signals", build_message("database", "down", changes[0][2], t[1], mirror_built=True),
                         "with the record mirror the confirmation runs, so BUY signals are not paused")
        back_text = build_message("database", "back", back[0][2], datetime(2026, 11, 1, 2, 30),
                                  kept={"reading": 290, "observation": 3000, "news": 6100}, left={})
        self.assertIn("The database is back, after 18 days.", back_text)   # 21 Mehr 21:00 to 10 Aban 06:00
        self.assertIn("Kept meanwhile, now written: 290 readings, 6,100 news items.", back_text)
        waiting = build_message("database", "back", back[0][2], datetime(2026, 11, 1, 2, 30),
                                kept={"reading": 290, "news": 6100}, left={"news": 40})
        self.assertIn("40 more are still being written", waiting)
        self.assertEqual(len(down_text) < 4096 and len(back_text) < 4096, True)

        world = {"since": t[1].isoformat(), "was_since": None, "reason": "fallback"}
        self.assertIn("World gold has not updated since 17:00; its last price is used.",
                      build_message("world gold", "down", world, t[2]))
        few = {"since": t[1].isoformat(), "was_since": None, "count": 2, "total": 11}
        self.assertIn("Only 2 of 11 platforms answered since 17:00; the discount needs three.",
                      build_message("platforms", "down", few, t[2]))
        self.assertEqual(status_line({}, t[0]), "Service: all working.")
        self.assertEqual(status_line({"database": {"ok": False, "since": held_since.isoformat()}}, t[1]),
                         "Service: the database out of reach since 21 Mehr, 21:00.")

    def test_54_the_watch_runs_first_and_status_reads_it(self):
        """The watch sees the run before anything that can end it -- a missing dollar raised in
        calculate_fair_price and ended runs before anything was stored -- sends each change once, and
        leaves the line Telegram's Status reads from the run's annotations."""
        import io
        from contextlib import redirect_stdout
        import main
        import alerts.telegram_service as ts
        from persistence import mirror, spool

        body = inspect.getsource(main.main)
        watch = body.index("_service_watch(state")
        self.assertLess(watch, body.index("validate_market_prices("), "before validation can end the run")
        self.assertLess(body.index("if usd is None:"), body.index("calculate_fair_price(world, usd)"),
                        "a missing dollar ends the run cleanly")
        self.assertIn("::notice title=service::", inspect.getsource(main._service_watch))
        worker = (REPO / "src" / "worker" / "telegram-trigger.js").read_text(encoding="utf-8")
        self.assertIn('a.title === "service"', worker)
        self.assertIn("await getServiceLine(env)", worker)

        self._spool_file()
        spool.hold("reading", {"snapshot": {"timestamp": datetime(2026, 10, 13, 17, 30)}, "platform_prices": []})
        sent, saved = [], []
        real = (mirror.reachable, mirror.unreachable_reason, mirror.built_at, ts.send_service, main.save_state)
        try:
            mirror.reachable = lambda: False
            mirror.unreachable_reason = lambda: "exceeded the data transfer quota"
            mirror.built_at = lambda: None
            ts.send_service = sent.append
            main.save_state = saved.append
            state = {}
            markets = {f"P{k}": {"status": "OK"} for k in range(9)}
            out = io.StringIO()
            with redirect_stdout(out):
                for hour in (12, 13, 14):
                    main._service_watch(state, datetime(2026, 10, 16, hour, 30), 4150.0, False, 270_000.0, markets)
            self.assertEqual(len(sent), 1, "one push for the outage")
            self.assertIn("out of reach since 21 Mehr, 21:00", sent[0])
            self.assertEqual(state["service"]["database"]["kept"], {"reading": 1})
            self.assertEqual(len(saved), 3, "the state is saved by the watch itself")

            # the spool began after the outage did (10-15): its oldest reading must not date it
            self._spool_file()
            spool.hold("reading", {"snapshot": {"timestamp": datetime(2026, 10, 15, 8, 34)}, "platform_prices": []})
            later_spool, sent[:] = {}, []
            with redirect_stdout(io.StringIO()):
                for hour in (12, 13):
                    main._service_watch(later_spool, datetime(2026, 10, 16, hour, 30), 4150.0, False, 270_000.0, markets)
            self.assertIn("out of reach since 21 Mehr, 21:00", sent[0], "dated from the record, not the spool")
            # once a run has seen Neon answer, a later outage is dated by its own runs
            mirror.reachable = lambda: True
            seen_ok = {}
            with redirect_stdout(io.StringIO()):
                main._service_watch(seen_ok, datetime(2026, 10, 20, 8, 30), 4150.0, False, 270_000.0, markets)
                mirror.reachable = lambda: False
                sent[:] = []
                for hour in (9, 10):
                    main._service_watch(seen_ok, datetime(2026, 10, 20, hour, 30), 4150.0, False, 270_000.0, markets)
            self.assertIn("out of reach since 23 Mehr", sent[0], "the spool's own reading of 10-15 dates it")
            self.assertIn("::notice title=service::Service: the database out of reach since 21 Mehr, 21:00.",
                          out.getvalue())
        finally:
            mirror.reachable, mirror.unreachable_reason, mirror.built_at, ts.send_service, main.save_state = real

    def test_55_an_old_news_item_is_not_stored_again(self):
        """The ingestion's dedup looked back 24 hours while the feeds keep items for weeks, so 330 of 2,294 rows
        from 09-22 were re-inserts (SP_C_HANDOFF.md 33.3, N1). It now asks which of the keys it fetched are
        stored, whatever their age (SP_D_HANDOFF.md section 45)."""
        import inspect as _inspect
        from collector.news import ingest
        from database import repository as repo
        from database.models import NewsEvent
        s = _test_get_session()
        try:
            s.query(NewsEvent).filter(NewsEvent.dedup_key.like("kpi55-%")).delete(synchronize_session=False)
            old = NOW - timedelta(days=30)
            s.add(NewsEvent(timestamp=old, source="goldbroker.com", dedup_key="kpi55-old", raw_headline="a month old",
                            event_type="UNKNOWN", relevance="UNKNOWN", classification_method="KEYWORD",
                            processed_at=old, created_at=old))
            s.commit()
        finally:
            s.close()
        real = repo.get_session
        try:
            repo.get_session = _test_get_session          # the repository's own binding, as test_38 does
            self.assertEqual(repo.get_stored_dedup_keys({"kpi55-old", "kpi55-new", None}), {"kpi55-old"})
            self.assertEqual(repo.get_stored_dedup_keys(set()), set())
        finally:
            repo.get_session = real
        body = _inspect.getsource(ingest.run_news_ingestion)
        self.assertIn("get_stored_dedup_keys(fetched_keys)", body)
        self.assertNotIn("hours=", body, "no time window")
        s = _test_get_session()
        try:
            s.query(NewsEvent).filter(NewsEvent.dedup_key.like("kpi55-%")).delete(synchronize_session=False)
            s.commit()
        finally:
            s.close()

    def test_56_one_money_reading_in_every_message(self):
        """Direction's money, the net as a share of buying and selling, and the money as times the usual week
        disagreed on 16% of days, and on 2026-10-03 itself: normal against unusual (SP_D_HANDOFF.md 46.1).
        gold_demand keeps the one reading; Direction, the evening and the room's report word it through
        alerts/gold_funds (section 47)."""
        import inspect as _inspect
        import json as _json
        import main
        from analysis import gold_demand as g
        from alerts import gold_funds, telegram_direction, telegram_paper
        from analysis.direction import DirectionPanel
        seed = _json.load(open(os.path.join(main.SEED_DIR, "gold_fund_daily.json"), encoding="utf-8"))["days"]
        days = [d for d in sorted(seed) if d <= "2026-10-03"]       # the week rd_money_week.py read
        dm = g.assess(days, [seed[d][:4] for d in days])
        net = [seed[d][0] - seed[d][2] for d in days]
        self.assertAlmostEqual(dm["money"]["value"], sum(net[-7:]) / (7 * sum(net[-257:-7]) / 250), places=9,
                               msg="the 7 days' net against 7 times the mean daily net of the 250 days before")
        self.assertEqual((dm["as_of"], dm["money"]["state"]), ("2026-10-03", "HIGH"))   # rd_money_week.py: rank 92%
        self.assertIn("usual_phrase", _inspect.getsource(telegram_direction._demand))
        self.assertIn("gold_funds import block", _inspect.getsource(telegram_paper.demand_block))
        self.assertIn("gold_funds import block", _inspect.getsource(main._evening_fallback))
        panel = DirectionPanel()
        panel.demand, panel.computed_at = dm, "2026-10-04T05:00:00"
        direction = telegram_direction._demand(panel)
        evening = "\n".join(gold_funds.block(dm))
        said = f"{dm['net_rial'] / 1e10:,.0f}B toman in, {dm['money']['value']:.1f} times the usual week"
        for text in (direction, evening):
            self.assertIn(said, text)
        self.assertIn("more than in 9 of 10 weeks", direction)
        self.assertIn("above the normal range", evening)

    def test_57_the_phone_reads_the_seeds_funds_and_its_live_rows_stay_research(self):
        """The phone's funds are the seed's, گنج included (SP_D_HANDOFF.md section 48), so production's history
        and the phone's days stay one series. Its live read of the session is asked only from 12:00 to 18:15
        Tehran, Saturday to Wednesday, and is stored as "tsetmc_live", which no production reader asks for."""
        import json as _json
        import re as _re
        import sys as _sys
        from datetime import datetime as _dt
        _sys.path.insert(0, str(REPO / "iran_node"))
        import node
        flows = _json.loads((REPO / "src" / "seed" / "gold_fund_flows.json").read_text(encoding="utf-8"))
        daily = _json.loads((REPO / "src" / "seed" / "gold_fund_daily.json").read_text(encoding="utf-8"))
        codes = {c for c, _s in node.GOLD_FUNDS}
        self.assertEqual(codes, set(flows["funds"]), "the phone's funds are the buyer-power seed's")
        self.assertEqual(codes, set(daily["funds"]), "and the demand seed's")
        self.assertNotIn("51200575796028449", codes | set(flows["funds"]) | set(daily["funds"]),
                         "no saffron anywhere (owner, 2026-10-18: 'take it out completely'; section 49)")
        self.assertIn("58514988269776425", codes, "گنج")
        asked = []
        real = node.requests.get

        class _R:
            def __init__(self, data):
                self.data = data

            def json(self):
                return self.data

        def fake(url, **k):
            asked.append(url)
            code = url.split("/")[-1] if "ClosingPrice" in url else url.split("/")[-3]
            if "ClientType" in url:
                return _R({"clientType": {key: 1.0 for key in node.LIVE_FLOW_KEYS}})
            traded = 0.0 if code == node.GOLD_FUNDS[0][0] else 5e6
            return _R({"closingPriceInfo": {"dEven": 20261018, "hEven": 130500, "pDrCotVal": 712000.0,
                                            "qTotTran5J": traded, "qTotCap": traded * 712000, "zTotTran": 900,
                                            "priceYesterday": 712879.0, "noise": "dropped"}})
        node.requests.get = fake
        try:
            self.assertEqual(node.read_tsetmc_live(tehran=_dt(2026, 10, 22, 13, 0)), [], "Thursday")
            self.assertEqual(node.read_tsetmc_live(tehran=_dt(2026, 10, 18, 11, 59)), [], "before the session")
            self.assertEqual(node.read_tsetmc_live(tehran=_dt(2026, 10, 18, 18, 16)), [], "after it")
            self.assertEqual(asked, [], "nothing is asked outside the session")
            rows = node.read_tsetmc_live(tehran=_dt(2026, 10, 18, 13, 5))
        finally:
            node.requests.get = real
        self.assertEqual(len(rows), len(node.GOLD_FUNDS) - 1, "a fund with no trade yet gives no row")
        self.assertEqual({r["source"] for r in rows}, {"tsetmc_live"})
        self.assertEqual(set(rows[0]["payload"]), set(node.LIVE_FLOW_KEYS) | set(node.LIVE_PRICE_KEYS))
        self.assertEqual(rows[0]["detail"], "20261018-130500")
        # production asks the node's table by exact source, and never for the live rows
        callers = []
        for path in (REPO / "src").rglob("*.py"):
            callers += _re.findall(r'get_node_rows\(\w+, "(\w+)"', path.read_text(encoding="utf-8"))
        self.assertTrue(callers)
        self.assertNotIn("tsetmc_live", callers)

    def test_58_the_old_signal_alert_is_parked_not_removed(self):
        """Owner, 2026-10-18: "can we just park it, i mean switch it off, and wait things to be cleared up? im
        cautious so we dont miss anything we built before" (SP_D_HANDOFF.md section 50). The switch is the one
        that gates the BUY/SELL alert; the decision is still made and recorded, and a signal not sent is
        logged."""
        import inspect as _inspect
        import json as _json
        import main
        cfg = _json.loads((REPO / "config" / "config.json").read_text(encoding="utf-8"))
        self.assertIs(cfg["email"]["send_alerts"], False)
        self.assertIn("signal_alerts_parked_2026_10_18", cfg["email"])
        body = _inspect.getsource(main.main)
        gate = body.index('should_send_alert = bool(signal and signal["signal"] in ("BUY", "SELL") and '
                          'email_cfg.get("send_alerts", True))')
        self.assertLess(body.index('state["alert_history"].append'), gate, "the signal is recorded before the gate")
        self.assertIn("parked, not sent", body[gate:gate + 600])
        self.assertIn("_send_buy_signal(markets", body[gate:], "the alert's code is kept, behind the switch")

    def test_59_only_scheduled_runs_save_state_and_they_run_one_at_a_time(self):
        """The external audit's A3, A4, A7 (SP_D_HANDOFF.md section 52): a user's run restored the state and saved
        it back after a scheduled run had saved a newer one, and its reading became the next scheduled run's
        previous premium. State and the mirror are restored by every run and saved by scheduled runs alone,
        also after a failed step, under the restore steps' own paths and keys; scheduled runs queue."""
        import re as _re
        text = (REPO / ".github" / "workflows" / "gold-monitor.yml").read_text(encoding="utf-8").replace("\r\n", "\n")
        blocks = {b.split("\n", 1)[0].strip(): b for b in text.split("\n      - name: ")[1:]}

        def field(block, name):
            m = _re.search(rf"^ +{name}: (.+)$", block, _re.M)
            return m.group(1).strip() if m else None

        def paths(block):
            m = _re.search(r"path: \|\n((?: {12}\S+\n)+)", block + "\n")
            return m.group(1).split() if m else [field(block, "path")]
        scheduled = "(github.event_name == 'schedule' || github.event.inputs.mode == 'analyze')"
        for restore, save in (("Restore State", "Save State"), ("Restore the record mirror", "Save the record mirror")):
            r, w = blocks[restore], blocks[save]
            self.assertEqual(field(r, "uses"), "actions/cache/restore@v4", restore)
            self.assertEqual(field(w, "uses"), "actions/cache/save@v4", save)
            self.assertEqual(paths(w), paths(r), "one list of paths, one cache")
            self.assertEqual(field(w, "key"), field(r, "key"))
            self.assertTrue(field(w, "if").startswith(f"always() && {scheduled}"), field(w, "if"))
        self.assertEqual(field(blocks["Save State"], "if"), f"always() && {scheduled}", "state is always saved")
        self.assertEqual(field(blocks["Save the record mirror"], "if"),
                         f"always() && {scheduled} && hashFiles('record_mirror.sqlite') != ''",
                         "the mirror only once it exists (section 54)")
        names = list(blocks)
        self.assertGreater(names.index("Save State"), names.index("Execute"))
        concurrency = text.split("\nconcurrency:\n", 1)[1].split("\n\n", 1)[0]
        self.assertIn(f"{scheduled} && 'gold-monitor-scheduled'", concurrency)
        self.assertIn("github.run_id", concurrency, "a user's run is never held up")
        self.assertIn("cancel-in-progress: false", concurrency)

    def test_60_the_phone_sets_a_refused_row_aside_and_stops_asking_for_closed_days(self):
        """The external audit's A9 (SP_D_HANDOFF.md section 52): a row Neon refused for its content stopped the
        queue behind it for good; Thursdays, Fridays and holidays were asked for every hour for a week. A refused
        row (SQLSTATE 22 or 23) is set aside and the rest go on; anything else still stops the queue; no closed
        day is asked on Thursday or Friday, and a day still without a record 3 days on is not asked again."""
        import io
        import json as _json
        from contextlib import redirect_stdout
        import sys as _sys
        import tempfile
        from datetime import datetime as _dt
        _sys.path.insert(0, str(REPO / "iran_node"))
        import node

        class _R:
            def __init__(self, status, body):
                self.status_code, self.body = status, body
                self.text = _json.dumps(body)

            def json(self):
                return self.body
        tmp = tempfile.mkdtemp()
        saved = {k: getattr(node, k) for k in ("SPOOL", "REJECTED", "LOG", "STATE_FILE", "LOCK", "ENV_FILE", "settings",
                                                 "read_daric", "read_compared", "read_tsetmc", "read_tsetmc_live")}
        real_post = node.requests.post
        try:
            for k, name in (("SPOOL", "spool"), ("REJECTED", "rejected"), ("LOG", "log"), ("STATE_FILE", "state"),
                            ("LOCK", "lock")):
                setattr(node, k, os.path.join(tmp, name))
            node.ENV_FILE = os.path.join(tmp, "env")
            open(node.ENV_FILE, "w").write("NEON_URL=postgresql://u:p@h/db\nNODE=t\n")
            rows = [{"source": "daric", "instrument": f"R{k}", "bid": None, "ask": None, "value": float(k),
                     "status": "OK", "detail": None, "payload": None} for k in range(4)]
            node.read_daric = lambda: rows[0]
            node.read_compared = lambda: rows[1:]
            node.read_tsetmc = lambda remember=True, any_minute=False: []
            node.read_tsetmc_live = lambda any_minute=False: []
            answers = {"R1": _R(400, {"code": "22P02", "message": "invalid input"})}
            node.requests.post = lambda url, **k: answers.get(_json.loads(k["data"])["params"][2], _R(200, {}))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(node.main([]), 0)
            self.assertEqual(node.load_spool(), [], "the other rows went")
            refused = [_json.loads(l) for l in open(node.REJECTED, encoding="utf-8")]
            self.assertEqual([r["instrument"] for r in refused], ["R1"])
            answers["R0"] = _R(402, {"message": "Your project has exceeded the data transfer quota"})
            with redirect_stdout(io.StringIO()):
                self.assertEqual(node.main([]), 2)
            self.assertEqual(len(node.load_spool()), 4, "the quota stops the queue: everything waits")
        finally:
            node.requests.post = real_post
            for k, v in saved.items():
                setattr(node, k, v)
        asked = []
        real_get = node.requests.get
        node.STATE_FILE = os.path.join(tmp, "state2")

        class _Clock:
            @staticmethod
            def now(tz=None):
                return _dt(2026, 10, 24, 6, 0, tzinfo=tz)       # Saturday 09:30 Tehran, minute < 15 after shift
        real_dt = node.datetime
        try:
            node.requests.get = lambda url, **k: asked.append(url) or _R(200, {"clientType": None})
            node.datetime = _Clock
            node.read_tsetmc(remember=True, any_minute=True)
            days = {u.rsplit("/", 1)[-1] for u in asked}
            self.assertNotIn("20261022", days, "Thursday")
            self.assertNotIn("20261023", days, "Friday")
            done = _json.load(open(node.STATE_FILE))["tsetmc_done"]
            self.assertTrue(all(k[:8] <= "20261021" for k in done), "only days 3 or more days old are given up")
            self.assertTrue(any(k.startswith("20261021:") for k in done))
        finally:
            node.requests.get, node.datetime = real_get, real_dt
            node.STATE_FILE = saved["STATE_FILE"]

    def test_61_the_audits_small_defects_stay_fixed(self):
        """The external audit's A15 (SP_D_HANDOFF.md section 53): PAPER's apply dropped the room's fund units and
        its share ignored them; the deep threshold counted a premium as a discount of the same size; one rule
        had two numbers (14 and 15 funds); Yahoo's yesterday's close passed as the spot price; and the fixed
        Tehran offset is checked against the tz database wherever one is present."""
        import inspect as _inspect
        from datetime import datetime as _dt, timedelta as _td
        from analysis import bubble_position as bp, gold_demand, paper, room
        from collector import kitco
        import timeutil
        book = paper.Book(cash=1e9, grams=10, units=5.0)
        for action in ("BUY", "SELL", "HOLD"):
            after = paper.apply(book, paper.Decision(action, 1 if action != "HOLD" else 0, 2e8, "t"))
            self.assertEqual(after.units, 5.0, action)
        self.assertAlmostEqual(book.share(2e8, fund_price=4e8), 2e9 / (1e9 + 2e9 + 2e9))
        t0 = _dt(2026, 9, 1)
        discounts = [(t0 + _td(hours=k), "scheduled", -(1 + k % 50) / 10) for k in range(200)]
        premiums = [(t0 + _td(hours=300 + k), "scheduled", +(1 + k % 50) / 10) for k in range(40)]
        self.assertEqual(bp.deep_discount_threshold(discounts + premiums), bp.deep_discount_threshold(discounts),
                         "a premium is not a discount of the same size")
        self.assertIs(room.FLOW_MIN_FUNDS, gold_demand.MIN_FUNDS, "one count of funds for a day")
        self.assertNotIn("previousClose", _inspect.getsource(kitco._try_yahoo_finance).split('"""')[-1])
        try:
            from zoneinfo import ZoneInfo
            tehran = ZoneInfo("Asia/Tehran")
        except Exception:
            tehran = None                  # no tz database here: the fixed offset is all there is
        if tehran is not None:
            for day in (_dt(2026, 3, 22, 12), _dt(2026, 6, 21, 12), _dt(2026, 10, 18, 12), _dt(2027, 1, 1, 12)):
                self.assertEqual(day.replace(tzinfo=tehran).utcoffset(), timeutil.TEHRAN_UTC_OFFSET, day)

    def test_62_the_funds_reach_every_message_and_say_why_when_not(self):
        """SP_D_HANDOFF.md section 54. tablokhani timed out from GitHub's runner on 7 of 16 runs of 2026-10-21 and
        the evening's funds block went out empty on three nights of four, saying nothing. Now: a longer read and a
        retry; one read a run, kept; the day's last complete reading kept in state for a run whose own read
        fails; the reason printed when there is none; Direction shows the same stand-in. And UPDATE keeps the
        three cheapest as its basis without the database, and the box's targets add up from its shown edges."""
        import inspect as _inspect
        from datetime import datetime as _dt
        import main
        from alerts import telegram_direction, telegram_paper
        from analysis import bubble_position as bp, gold_demand
        from collector import tablokhani as tk
        self.assertGreaterEqual(tk.TIMEOUT[1], 30)
        self.assertGreaterEqual(tk.TRIES, 2)
        calls, real = [], tk.requests.get

        def down(url, **k):
            calls.append(url)
            raise tk.requests.exceptions.ReadTimeout("slow")
        tk._last = None
        tk.requests.get = down
        try:
            first = tk.collect()
            n = len(calls)
            again = tk.collect()
        finally:
            tk.requests.get, tk._last = real, None
        self.assertEqual(n, 2 * tk.TRIES, "both endpoints, each tried TRIES times")
        self.assertIs(again, first, "a run does not wait for a failed read twice")
        flows = {f: (1e12, 4000.0, 0.9e12, 2000.0) for f in tk.GOLD_FUNDS}
        now = _dt(2026, 10, 21, 17, 30)                                     # 21:00 Tehran
        state = {}
        saved = tk.collect
        try:
            tk.collect = lambda: {"flows": flows, "errors": []}
            main._keep_funds_reading(state, _dt(2026, 10, 21, 16, 30))      # 20:00 Tehran, complete
            tk.collect = lambda: {"flows": {}, "errors": ["smart-money-averages: ReadTimeout"]}
            demand, source = main._funds_stand_in(now, state)
            self.assertTrue(demand and source == "tablokhani's reading of 20:00", source)
            stale = {main.FUNDS_KEPT: dict(state[main.FUNDS_KEPT], at="2026-10-20T16:30:00")}
            demand, source = main._funds_stand_in(now, stale)
            self.assertEqual(demand, {})
            self.assertIn("smart-money-averages: ReadTimeout", source, "the reason, printed")
        finally:
            tk.collect = saved
        self.assertIn("gold funds {('yes, ' + source) if funds else ('no: ' + source)}",
                      _inspect.getsource(main._evening_fallback))
        self.assertIn("_funds_stand_in(now, load_state())", _inspect.getsource(main._send_direction_report))
        self.assertIn('dm.get("label")', _inspect.getsource(telegram_direction._demand))
        self.assertIn("_keep_funds_reading(state, now)", _inspect.getsource(main.main))
        self.assertIsNotNone(gold_demand.MIN_FUNDS)
        # UPDATE's basis without the database: the three cheapest, ranks absent
        M = 1e7
        prices = {"A": 25.70, "B": 25.80, "C": 25.80, "D": 25.82, "E": 26.12}
        markets = {k: {"status": "OK", "price": v * M} for k, v in prices.items()}
        val = bp.resolve_relative_valuation(None, markets=markets, fair_price=26.36 * M)
        self.assertEqual((val.basis_count, val.status), (3, "INSUFFICIENT_DATA"))
        self.assertAlmostEqual(val.gap, (25.7667 / 26.36 - 1) * 100, places=2)
        self.assertIsNone(val.bigger_than)
        # the box: its targets from the edges as shown
        found = {"ranges": [(_dt(2026, 10, 1).date(), _dt(2026, 10, 15).date(), 252_655_000.0, 267_390_000.0, True)],
                 "tests": [], "flag": None, "events": []}
        lines = telegram_paper.pattern_lines(found)
        self.assertEqual(lines[1:], ["  Close above 26.74M: opens the road to 28.21M",
                                     "  Close below 25.27M: may lead to 23.80M"])
        self.assertIn("% drop: on days like today", _inspect.getsource(telegram_direction._buy_or_wait))

    def test_63_one_vocabulary_on_every_surface_and_the_chart(self):
        """The owner's answers of 2026-10-22 on the contradictions of 26 Mehr (SP_D_HANDOFF.md 54.6, 55): "50D EMA"
        and "50D MA" named apart; one decimal; "was"; the box on closes with its highest high; the prices labelled
        by basis and the chart's words the messages' words; "parity" for "fair value"; Persian dates everywhere."""
        import inspect as _inspect
        import re as _re
        from datetime import date as _date
        from alerts import chart, helpers, telegram_direction, telegram_paper
        from caluclator import patterns
        # parity: no reader-facing "fair value" left in the Telegram surfaces (comments aside)
        for path in (REPO / "src" / "alerts").glob("telegram*.py"):
            code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
            strings = _re.findall(r'f?"[^"\n]*"', code)
            self.assertFalse([x for x in strings if "fair value" in x.lower()], path.name)
        # Persian dates: the shared footer, the chart's axis
        self.assertRegex(helpers.format_timestamp(), r"^\d{1,2} [A-Z][a-z]+ 14\d\d, \d\d:\d\d$")
        self.assertIn("persian_day(ds[t])", _inspect.getsource(chart.render))
        self.assertNotIn('strftime("%m-%d")', _inspect.getsource(chart.render))
        # the averages named apart, on the chart as in the messages
        render = _inspect.getsource(chart.render)
        self.assertIn('label="20D EMA"', render)
        self.assertIn('label="50D EMA"', render)
        trend = _inspect.getsource(telegram_direction._trend)
        self.assertIn("'20D EMA'", trend)
        self.assertIn("'50D EMA'", trend)
        watch = _inspect.getsource(telegram_direction._watch)
        self.assertIn("its 50D MA", watch)
        code = [l for l in (watch + trend).splitlines() if not l.strip().startswith("#")]
        self.assertFalse([l for l in code if "50-day" in l], "no 50-day left in the words")
        self.assertIn("(market, tgju)", _inspect.getsource(telegram_direction._head))
        # the evening in the same words, and the chart's marks named as the caption names them
        reading = {"price": 258_900_000.0, "live": True, "as_of": _date(2026, 10, 17), "phase": "MARKUP",
                   "channel": None, "swing": None, "trend_lines": {"support": 230_000_000.0, "resistance": 278_500_000.0},
                   "ema20": (1.04, 2.2), "ema50": (7.71, 9.2),
                   "patterns": {"ranges": [(_date(2026, 9, 29), _date(2026, 10, 17), 252_700_000.0, 267_400_000.0, True)],
                                "tests": [_date(2026, 10, 13)], "flag": None, "events": [], "box_high": 268_400_000.0}}
        text = _re.sub(r"</?[bi]>", "", telegram_paper.build_evening_message(_date(2026, 10, 18), reading))
        self.assertIn("1.0% above the 20D EMA (was 2.2%), 7.7% above the 50D EMA", text)
        self.assertIn("Touched the 20D EMA on 21 Mehr", text)
        self.assertIn("In a box since 7 Mehr: closes between 25.27M and 26.74M (highest high 26.84M)", text)
        self.assertIn("Support trend line 23.00M, resistance trend line 27.85M", text)
        self.assertEqual((patterns.name("EMA20 TEST"), patterns.name("RANGE BREAKOUT")), ("20D EMA touch", "box breakout"))
        # a box's break is told, without a rate, for two weeks (section 56): 29 Mehr's close above 26.74M
        broke = {"ranges": [(_date(2026, 9, 29), _date(2026, 10, 20), 252_700_000.0, 267_400_000.0, False)],
                 "tests": [], "flag": None, "as_of": _date(2026, 10, 21),
                 "events": [(_date(2026, 10, 21), "RANGE BREAKOUT", 267_400_000.0, 282_100_000.0, 252_700_000.0)]}
        self.assertEqual(telegram_paper.pattern_lines(broke),
                         ["Broke up out of the box (25.27M-26.74M) on 29 Mehr: target 28.21M while above 25.27M"])
        later = dict(broke, as_of=_date(2026, 11, 8))
        self.assertEqual(telegram_paper.pattern_lines(later), [], "told for two weeks")
        levels = _inspect.getsource(telegram_direction._levels)
        self.assertIn('f"Resistance level {', levels)
        self.assertIn('f"Support level {', levels)

    def test_64_no_telegram_surface_uses_a_word_the_vocabulary_forbids(self):
        """The owner, 2026-10-29: "we had agreed upon a wording list ... is there a dict list to be referenced?"
        The list is the vocabulary table in skills/telegram-product.md; its rows marked "test" are enforced here
        over the text the Telegram surfaces and the chart write (docstrings and comments aside). The parked
        legacy alert and e-mails (alerts/telegram.py, helpers' SP-A blocks, resend_mail) are left to SP-E
        (SP_D_HANDOFF.md section 64)."""
        import ast
        import re as _re
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        with open(os.path.join(root, "skills", "telegram-product.md"), encoding="utf-8") as f:
            table = f.read()
        rows = [[c.strip() for c in line.strip().strip("|").split("|")]
                for line in table.split("### Vocabulary", 1)[1].split("\n## ", 1)[0].splitlines()
                if line.startswith("|") and not line.startswith("|---")][1:]
        never = sorted({w.strip() for r in rows if len(r) == 4 and r[3] == "test" for w in r[2].split(",")})
        self.assertIn("parity", never)
        self.assertIn("fair value", never)
        self.assertGreaterEqual(len(never), 12)
        surfaces = ("telegram_update_v1", "telegram_analyze", "telegram_signal", "telegram_service",
                    "telegram_direction", "telegram_paper", "telegram_pulse", "gold_funds", "chart")
        found = []
        for module in surfaces:
            path = os.path.join(root, "src", "alerts", f"{module}.py")
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            docstrings = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)
                          and isinstance(n.value, ast.Constant)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                    for word in never:
                        if _re.search(rf"\b{_re.escape(word)}\b", node.value, _re.IGNORECASE):
                            found.append(f"{module}:{node.lineno} {word!r} in {node.value[:50]!r}")
        self.assertEqual(found, [])

    def test_65_the_discount_rests_on_the_gram_platforms_everywhere(self):
        """The owner, 2026-10-29: two kinds of platform, grams and gold products ("Eligold - Hoorgold - Parasteh
        and Mio gold"), and "fix now the discounts". One definition (platforms.py); every reader of the discount,
        its record, the push's corroboration and the BUY's second platform filters on it (SP_D_HANDOFF.md 65)."""
        import inspect as _inspect
        import platforms
        import main
        from analysis import analyze_report, bubble_position, confirmation
        from alerts import telegram_signal, telegram_update_v1
        self.assertEqual(platforms.PRODUCT_PLATFORMS, {"Eligold", "HoorGold", "Parasteh", "MioGold"})
        self.assertTrue(platforms.is_gram("Invi"), "Invi is a gram platform (owner, 2026-10-29)")
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
        defined = []
        for folder, _dirs, files in os.walk(root):
            for f in files:
                if f.endswith(".py"):
                    with open(os.path.join(folder, f), encoding="utf-8") as fh:
                        if "PRODUCT_PLATFORMS =" in fh.read():
                            defined.append(f)
        self.assertEqual(defined, ["platforms.py"], "one definition")
        for reader in (bubble_position._basis_series, confirmation.second_gap_series):
            self.assertIn("is_gram(name)", _inspect.getsource(reader), reader.__name__)
        self.assertIn("is_gram(name)", _inspect.getsource(analyze_report))
        self.assertIn("gram_markets(markets)", _inspect.getsource(bubble_position.resolve_relative_valuation))
        self.assertIn("gram_markets(markets)", _inspect.getsource(main._evaluate_deep_discount_push))
        self.assertIn("gram_markets(markets)", _inspect.getsource(telegram_update_v1._cheapest_platforms))
        self.assertIn("gram_markets(markets)", _inspect.getsource(telegram_signal))
        # the BUY's second platform is a gram platform even when a gallery quotes lower
        markets = {"MioGold": {"status": "OK", "price": 90.0}, "HoorGold": {"status": "OK", "price": 91.0},
                   "Milli": {"status": "OK", "price": 95.0}, "Goldika": {"status": "OK", "price": 97.0}}
        self.assertEqual(confirmation.second_cheapest(markets, 100.0)[0], "Goldika")

    def test_66_the_outages_writes_are_held_for_review_when_neon_returns(self):
        """The owner, 2026-10-30: "we should only write back the data we will use and is trustworthy, not
        everything that we have collected so far ... clean up, and once confirmed move it to neon." The write-back
        waits for config spool.write_back; the SERVICE notice says the writes are held (SP_D_HANDOFF.md 70)."""
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from datetime import datetime
        import main
        from alerts.telegram_service import build_message
        from persistence import spool
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "config.json"),
                  encoding="utf-8") as f:
            # confirmed by the owner on 2026-10-30: readings, observations and daily inputs; news held (73)
            self.assertEqual(json.load(f)["spool"]["write_back"], ["reading", "observation", "candles"])
        self.assertEqual(main._write_back_kinds(), {"reading", "observation", "candles"})
        folder = tempfile.mkdtemp()
        os.environ["RECORD_SPOOL_FILE"] = os.path.join(folder, "spool.jsonl")
        self.addCleanup(os.environ.pop, "RECORD_SPOOL_FILE", None)
        spool.hold("news", {"dedup_key": "kpi66", "timestamp": datetime(2026, 10, 20)})
        asked = []
        real = main.get_session
        try:
            main.get_session = lambda: asked.append(1)
            with redirect_stdout(io.StringIO()) as out:
                main._flush_spool({"spool": {"write_back": False}})
        finally:
            main.get_session = real
        self.assertEqual(asked, [], "the database is not even opened")
        self.assertEqual(len(spool.held()), 1, "the write stays held")
        self.assertIn("kept for review, not written back", out.getvalue())
        self.assertTrue(main._write_back_on({}), "without the key, as before")
        record = {"since": "2026-11-01T02:30:00", "was_since": "2026-10-13T17:30:00"}
        text = build_message("database", "back", record, datetime(2026, 11, 1, 3, 30),
                             kept={"reading": 300, "news": 400}, left={"reading": 300, "news": 400},
                             held_for_review=True)
        self.assertIn("held for a check before they are written", text)
        self.assertNotIn("still being written", text)
        # only some kinds: news alone held, the database not opened, and the notice says what was kept
        asked.clear()
        try:
            main.get_session = lambda: asked.append(1)
            with redirect_stdout(io.StringIO()) as out:
                main._flush_spool({"spool": {"write_back": ["reading", "observation", "candles"]}})
        finally:
            main.get_session = real
        self.assertEqual((asked, len(spool.held())), ([], 1), "nothing of the kinds written back is held")
        self.assertIn("held writes of other kinds kept", out.getvalue())
        text = build_message("database", "back", record, datetime(2026, 11, 1, 3, 30),
                             kept={"reading": 300, "news": 400}, left={}, held_kinds={"news"})
        self.assertIn("Kept meanwhile: 300 readings, now written.", text)
        self.assertIn("400 news items kept for a check, not written.", text)
        # a flush keeps the entries it is told to keep, after the ones it could not write
        held = spool.held()
        written = spool.flush(None, {}, [], keep=held)
        self.assertEqual((written, spool.held()), ((0, 0, 0), held))

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
