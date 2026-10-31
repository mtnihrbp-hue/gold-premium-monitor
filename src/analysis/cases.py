"""What followed past strikes and deals, for the lens (SP_D_HANDOFF.md sections 84-86). Reads the case library
src/seed/cases.json (built by research/build_cases.py from tgju's closes) and never recomputes it: a past case's
outcome does not change. Each count is read against any day (the seed's base), so a case is not read alone.
Three cases are cases, not statistics: the lens prints the counts, never a probability made from them."""

import json
import os
import statistics as st

SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seed", "cases.json")
SAME_DIRECTION = 0.15            # a share within this of any day's is "the usual direction"
BIGGER = 1.3                     # a typical move this many times any day's is "bigger"


def load(path=SEED):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def summary(seed, kind):
    """The cases of one kind against any day: counts, typical sizes, the cases that went lower."""
    cases = [c for c in seed["cases"] if c["kind"] == kind and c.get("gold18_40") is not None]
    if not cases:
        return None
    higher = [c for c in cases if c["gold18_40"] > 0]
    lower = [c for c in cases if c["gold18_40"] <= 0]
    first_week = min(cases, key=lambda c: c.get("gold18_5") if c.get("gold18_5") is not None else 0)
    base = seed["base"]
    typical = st.median(abs(c["gold18_40"]) for c in cases)
    return {"n": len(cases), "higher": len(higher), "lower": lower, "typical_abs": typical,
            "base_share": base["higher_40_share"], "base_typical": base["typical_abs_move_40"],
            "usual_direction": abs(len(higher) / len(cases) - base["higher_40_share"]) <= SAME_DIRECTION,
            "bigger": typical >= BIGGER * base["typical_abs_move_40"],
            "lower_with_dollar_down": bool(lower) and all((c.get("dollar_40") or 0) < 0 for c in lower),
            "worst_first_week": first_week if (first_week.get("gold18_5") or 0) < 0 else None,
            "shut": [c for c in cases if c.get("shut_days")]}
