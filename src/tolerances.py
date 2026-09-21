"""Shared numeric tolerances.

One definition each, for the same reason `timeutil.py` holds one definition of local
time: a constant copied into four modules is four constants that currently agree.
This project has now been bitten by that shape three times -- `Deep discount`
carrying two numbers, the percentile formula existing in three files, and
`valuation_state` disagreeing with the band stored in its own row.

Found by the SP-C.16 audit, which counted the module-level numeric constants in
`src/` and looked for repeats:

    0.05  UNCHANGED_DEADBAND_PP        analysis/analyze_report.py
          UNCHANGED_DEADBAND_PP        analysis/bubble_position.py
          INCONCLUSIVE_DEADBAND_PP     analysis/decision_scorecard.py
          BUBBLE_MOVEMENT_DEADBAND_PP  update/baseline_resolver.py

    0.5   COMPARABLE_BAND_FRACTION     analysis/analyze_report.py
          COMPARABLE_BAND_FRACTION     analysis/bubble_position.py

Four names for one idea, across four modules, none importing another. Nothing had
gone wrong yet, which is the point: it had not gone wrong *yet*.

This module sits at the `src/` root so every layer can import it without inverting
the dependency direction, exactly as `timeutil` does.
"""

# A change in the discount smaller than this is reported as no change.
#
# 0.05 percentage points is a display-resolution decision, not a market measurement:
# every surface prints the discount to two decimals, so a move below this rounds to
# nothing a reader could see. It is deliberately *not* tied to measured noise -- the
# 90th-percentile reading-to-reading step is 0.46 pp, nine times larger, and calling
# everything below that "unchanged" would hide most real movement.
#
# The decision scorecard uses the same value to mean "too small to score either way",
# which is the same idea seen from the other end: a move a reader cannot see is not
# evidence for or against a decision.
UNCHANGED_DEADBAND_PP = 0.05

# How close a past reading must be to the current one to count as "at this level",
# as a fraction of the window's own spread rather than a fixed distance in
# percentage points, so it widens when the market is volatile and narrows when it is
# calm.
#
# Half the interquartile spread: wide enough that ANALYZE's comparable band holds
# roughly a third of the window rather than a handful of readings, narrow enough that
# "this level" still means something. On 2026-09-21 it produced 100 comparable
# readings out of 265.
COMPARABLE_BAND_FRACTION = 0.5
