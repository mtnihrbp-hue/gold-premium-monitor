"""The valuation leg of the decision engine.

A rank decides which discounts are cheap. A direction gate decides whether the label
may be used at all.

--------------------------------------------------------------------------------
Why this is not a fixed threshold any more
--------------------------------------------------------------------------------

It was one until 2026-09-21, and it never once changed its answer.

    valuation_state                 CHEAP  364 / 364 rows
    stored premium_percent          -8.19% to -1.52%
    rows shallower than buy_premium  0

The threshold that decided CHEAP sat 0.02 pp outside the entire observed range of 438
readings. It had never been crossed, in either direction, so the column was a constant
wearing the costume of a classifier -- the same failure as `regime_state` reading PANIC
on every snapshot and `relevance` reading UNKNOWN on every article.

The cost was not a wrong answer, it was an absent one. `valuation_state` is the first
input to the conflict matrix (Valuation -> Momentum -> Structure -> Conflict ->
Candidate -> Hysteresis -> Final). One of three inputs carried no information for the
whole record, so every decision the engine has ever made rested on two legs while
reporting three. The decision scorecard measured an edge of 0.0 and was right to.

Worse, the replacement already existed. SP-C.2 built the percentile band, stored it in
`market_states.valuation_context_json` beside the column, and wired it to nothing. The
two labels disagreed on 114 of the 134 rows that carry both -- CHEAP and EXPENSIVE, the
same row, the same moment -- and the defect index recorded the class as fixed.

--------------------------------------------------------------------------------
Why a rank, and why a gate as well
--------------------------------------------------------------------------------

A rank cannot go stale. It answers "how does this reading compare with the last thirty
days" rather than "is this reading past a number someone chose in August", and a number
someone chose in August has gone stale four times in this codebase.

But a rank alone is not enough, and wiring one in without a gate would have been a
serious mistake. A percentile-EXPENSIVE reading means "less discounted than usual" --
it does **not** mean the market is above fair value. The conflict matrix turns
EXPENSIVE plus WEAKENING into SELL. Fed a bare rank, this engine would have issued SELL
on a market trading 1.6% *below* fair value.

So each label carries the direction it asserts, which is the rule from
`LESSONS_LEARNED.md` section 12: a magnitude is not a direction.

    CHEAP       rank in the cheapest band   AND   actually below fair value
    EXPENSIVE   rank in the dearest band    AND   actually above fair value
    FAIR        anything else
    UNKNOWN     no rank -- too little history to place the reading

Measured over the record, the direction gate on the sell side never opens: the highest
premium ever stored is -1.52%, so EXPENSIVE cannot occur and SELL cannot fire. That is
correct rather than degenerate. The market has genuinely never traded above fair value,
and a classifier that declines to call it expensive is answering accurately. The
distinction matters and is the subject of `LESSONS_LEARNED.md` section 13: a constant
output is only a defect when the world contained the other case and the classifier
missed it.

--------------------------------------------------------------------------------
What the record says this changes
--------------------------------------------------------------------------------

Replayed across all 366 stored decisions, rebuilding each rank from the settled
non-user window as it stood at that moment:

    valuation_state   CHEAP 366          ->  CHEAP 111, FAIR 222, UNKNOWN 33
    candidate         BUY 131, WAIT 235  ->  BUY 63, WAIT 270, UNKNOWN 33
    EXPENSIVE                            ->  0, as above

The 33 UNKNOWNs are the opening month, before the window reaches
`MIN_OBSERVATIONS`. They abstain rather than guess, which is the fail-safe law.

And the separation is real. Taking one observation per local day per state to remove
the overlap between hourly readings inside a 24-hour horizon:

    CHEAP   28 days   discount narrowed 78.6% of the time   mean +0.65 pp
    FAIR    39 days   discount narrowed 41.0% of the time   mean -0.32 pp

Stated as description, not as a validated edge: it is in-sample, it is one market
regime over forty days, and `skills/market-analyst.md` forbids manufacturing confidence
from a small sample. The honest claim is narrower and sufficient -- the fixed threshold
could not produce this table at all, because one bucket has nothing to be compared
with.
"""

from typing import Optional


def classify_valuation(
    percentile: Optional[int],
    premium: Optional[float],
    *,
    cheap_rank: int,
    expensive_rank: int,
    buy_at: float,
    sell_at: float,
) -> str:
    """Return CHEAP | FAIR | EXPENSIVE | UNKNOWN.

    Pure, and every bound is passed in rather than read from configuration here, so
    this can be reasoned about and tested without a database or a config file, and so
    there is exactly one place the decision and the reader's band can disagree: the
    caller, which passes the same bounds to both.

    Args:
        percentile: rank of `premium` within its own recent window, 0-100. None
            means the window was too short to place the reading.
        premium: the signed premium, negative for a discount.
        cheap_rank: ranks strictly below this are in the cheap band.
        expensive_rank: ranks at or above this are in the expensive band.
        buy_at: the premium must be at or below this to be called CHEAP. A direction
            gate, not a trigger -- it keeps the word attached to the side of fair
            value it claims.
        sell_at: the premium must be at or above this to be called EXPENSIVE.
    """
    if percentile is None or premium is None:
        return "UNKNOWN"
    if percentile < cheap_rank and premium <= buy_at:
        return "CHEAP"
    if percentile >= expensive_rank and premium >= sell_at:
        return "EXPENSIVE"
    return "FAIR"
