"""DIRECTION's forecast ledger: did what it said happen? (SP-D, section 49).

The owner's condition for letting the system learn from itself (2026-10-03): "do we catch
proper things to evaluate and avoid mistakes?" The safeguards, in order:

1. Every forecast a panel shows is stored with it, before its outcome exists, and is
   never rewritten (direction_snapshots).
2. It is resolved against tgju's daily candles only, never against our own platform
   readings, so the system cannot grade itself on the data it is predicting from.
3. One forecast per Tehran day enters the record (the latest slot), so two panels on the
   same day do not count twice.
4. The rates themselves are re-counted from the whole history at every computation, so
   each completed day changes them; nothing is fitted or tuned on the live record.
5. The gate: a figure keeps its place in the message only while its live record holds
   up -- the new-high rate must beat the plain base rate (Brier score), the 20-day range
   must hold between RANGE_COVERAGE_LOW and RANGE_COVERAGE_HIGH of outcomes, and a bullish
   stance must be followed by a rise more often than the record's all-days rate. Below
   GATE_MIN_RESOLVED resolved days the figure is shown as "learning", with its count.
   A figure that fails is demoted: the message falls back to the base rate or marks it,
   and the alarm is printed in the run log.
"""

from datetime import date, datetime

GATE_MIN_RESOLVED = 30
GATE_WINDOW = 120                   # the most recent resolved days the gate judges
RANGE_COVERAGE_LOW, RANGE_COVERAGE_HIGH = 65.0, 92.0    # a 10-90% range should hold ~80%
BULLISH = ("STRONG BULLISH", "BULLISH")


def resolve_forecast(forecast, dates, close):
    """The outcome of one forecast once `horizon` candles exist after its from_date, else
    None. `dates`/`close`: tgju's completed candles, oldest first."""
    start = date.fromisoformat(forecast["from_date"])
    after = [k for k, d in enumerate(dates) if d > start]
    horizon = forecast["horizon"]
    if len(after) < horizon:
        return None
    window = [close[k] for k in after[:horizon]]
    end = window[-1]
    key = forecast["key"]
    if key == "new_high_20d":
        return {"hit": bool(max(window) > forecast["record"]), "max": max(window)}
    if key in ("range_20d", "range_60d"):
        low, mid, high = forecast["price"]
        return {"close": end, "inside": bool(low <= end <= high), "below_mid": bool(end <= mid),
                "above": bool(end > high)}
    if key == "stance_20d":
        return {"close": end, "higher": bool(end > forecast["from_price"]),
                "move_pct": (end / forecast["from_price"] - 1) * 100}
    return None


def resolve_pending(session, now=None):
    """Resolve every stored forecast whose horizon has passed. Returns the count resolved.
    Never raises: the ledger must not stop the run that feeds it."""
    from analysis.direction import GOLD, load_series
    from database.repository import pending_direction_snapshots, save_direction_outcomes

    now = now or datetime.utcnow()
    resolved = 0
    try:
        dates, _, _, close = load_series(session, GOLD)
        for row in pending_direction_snapshots(session):
            outcomes = dict(row.outcomes or {})
            for forecast in row.forecasts or []:
                if forecast["key"] in outcomes:
                    continue
                outcome = resolve_forecast(forecast, dates, close)
                if outcome is not None:
                    outcomes[forecast["key"]] = outcome
                    resolved += 1
            if outcomes != (row.outcomes or {}):
                complete = all(f["key"] in outcomes for f in row.forecasts or [])
                save_direction_outcomes(session, row, outcomes, complete, now)
    except Exception as e:
        print(f"Direction ledger: resolve failed: {e}")
    return resolved


def _one_per_day(rows):
    """The latest stored panel of each Tehran day."""
    latest = {}
    for row in rows:
        if row.local_date not in latest or row.computed_at > latest[row.local_date].computed_at:
            latest[row.local_date] = row
    return [latest[d] for d in sorted(latest)]


def assess(rows):
    """The live track record of resolved forecasts, and the gate's verdict on each figure.

    `rows`: stored panels with outcomes (any order). Returns {figure: {...}} where each
    figure carries n, its live measure, and state LEARNING, OK or DEMOTED.
    """
    days = _one_per_day(rows)[-GATE_WINDOW:]
    pairs = {}
    for row in days:
        for forecast in row.forecasts or []:
            outcome = (row.outcomes or {}).get(forecast["key"])
            if outcome is not None:
                pairs.setdefault(forecast["key"], []).append((forecast, outcome))

    record = {}
    nh = [(f, o) for f, o in pairs.get("new_high_20d", []) if f.get("prob") is not None and f.get("base") is not None]
    if nh:
        hits = [1.0 if o["hit"] else 0.0 for _, o in nh]
        brier = sum((f["prob"] / 100 - h) ** 2 for (f, _), h in zip(nh, hits)) / len(nh)
        brier_base = sum((f["base"] / 100 - h) ** 2 for (f, _), h in zip(nh, hits)) / len(nh)
        record["new_high"] = {"n": len(nh), "hit_pct": sum(hits) / len(nh) * 100,
                              "mean_prob": sum(f["prob"] for f, _ in nh) / len(nh),
                              "brier": brier, "brier_base": brier_base,
                              "state": _state(len(nh), brier <= brier_base)}
    rg = pairs.get("range_20d", [])
    if rg:
        inside = sum(o["inside"] for _, o in rg) / len(rg) * 100
        record["range20"] = {"n": len(rg), "inside_pct": inside,
                             "above_pct": sum(o["above"] for _, o in rg) / len(rg) * 100,
                             "state": _state(len(rg), RANGE_COVERAGE_LOW <= inside <= RANGE_COVERAGE_HIGH)}
    st = pairs.get("stance_20d", [])
    if st:
        everyone = sum(o["higher"] for _, o in st) / len(st) * 100
        bull = [o for f, o in st if f["label"] in BULLISH]
        bull_pct = sum(o["higher"] for o in bull) / len(bull) * 100 if bull else None
        record["stance"] = {"n": len(st), "bullish_n": len(bull), "bullish_higher_pct": bull_pct,
                            "all_higher_pct": everyone,
                            "state": _state(len(bull), bull_pct is not None and bull_pct > everyone)}
    return record


def _state(n, holds):
    if n < GATE_MIN_RESOLVED:
        return "LEARNING"
    return "OK" if holds else "DEMOTED"


def apply_gate(panel, record):
    """Attach the record to the panel and demote what fails. Returns the alarms raised."""
    panel.record = record
    alarms = []
    nh = record.get("new_high")
    if nh and nh["state"] == "DEMOTED":
        alarms.append(f"new-high rate did not beat the base rate on its last {nh['n']} resolved days "
                      f"(Brier {nh['brier']:.3f} vs {nh['brier_base']:.3f})")
    rg = record.get("range20")
    if rg and rg["state"] == "DEMOTED":
        alarms.append(f"20-day range held {rg['inside_pct']:.0f}% of its last {rg['n']} outcomes")
    st = record.get("stance")
    if st and st["state"] == "DEMOTED":
        alarms.append(f"bullish stances rose {st['bullish_higher_pct']:.0f}% of the time against "
                      f"{st['all_higher_pct']:.0f}% for all days")
    panel.record["alarms"] = alarms
    return alarms
