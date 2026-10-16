"""The decision engine replayed on the hourly record: did its BUYs pick better moments to buy?
(SP-D, SP_D_HANDOFF.md section 39; the owner, 2026-10-16: "before rebuilding the decision engine, let
me know your plan in details ... what the R&D says").

Why. The engine's only score -- 55.2% against always-WAIT, an edge of 0.0 (SP_C_HANDOFF.md section 6)
-- was taken while a latch held every decision at WAIT: a constant scored against a constant, as SP-C
itself recorded (its section 16.1, "untested in production, not failed"). It has never been scored
since. Production's record is out of reach until 11-01; research/data/hourly.json (2026-08-04 to
10-04) is the copy on this machine.

Rules, fixed before the run:
- Data: hourly.json in an in-memory database, every row a scheduled reading (fair value, the premium
  from the cheapest platform, the dollar, world gold, each platform's price).
- The engine: production's own functions at this commit, each reading judged at its own time from the
  readings before it:
    analysis.bubble_position.resolve_decision_valuation   the rank over settled days
    analysis.confirmation.resolve_signal_confirmation     second platform, today's dollar; world gold live
    caluclator.signal_state.build_signal_state            direction, momentum, structure, the matrix
    caluclator.signals.apply_hysteresis                   its 24-hour cooldown, on the replay's clock
  Thresholds from config/config.json.
- What a buyer pays: the mean of the three cheapest platforms (UPDATE's basis). The outcome at +h hours
  (h = 24 and 72) is the first reading at least h hours later, within 12 hours, against this one.
- Rules compared, each by episodes (a start when the previous reading was not in it, and 12 hours or
  more after the rule's last start):
    candidate BUY   the matrix's BUY, before the confirmation
    final BUY       after the confirmation and the cooldown: what would have been sent
    deep zone       the push's own level (push_trigger.resolve_push_thresholds), the simple rule to beat
  Control: every reading (buying at any moment).
- Reported: per rule, the episodes and the mean and median +h basis change after each first reading,
  against the control; the scorecard's own rule (BUY right when the discount then shrank, WAIT right
  when it grew; analysis/decision_scorecard.py) on every reading, against always-BUY and always-WAIT.
- Verdict, decided now: a rule "picks better moments" only when its episodes' mean +24h basis change
  is at least 0.5 pp above the control's on at least 8 episodes. Fewer episodes: INSUFFICIENT.
  Otherwise: NO EDGE.
- Added after the first run, before its own (committed first): the cost of following the engine. A
  reader deciding on a Tehran day whose first reading says WAIT, who waits for the engine's next final
  BUY and buys then, against buying at that first reading: the basis change between the two, per day
  (one a day, so days do not overlap). Days with no later BUY in the record are censored and counted.

Run: python research/rd_engine_replay.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from statistics import mean, median

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database.models import Base, MarketSnapshot, PlatformPrice  # noqa: E402

HORIZONS = (24, 72)
GAP_HOURS = 12
MIN_EPISODES = 8
EDGE_PP = 0.5


def load():
    rows = json.load(open(os.path.join(HERE, "data", "hourly.json"), encoding="utf-8"))
    rows = [r for r in rows if r.get("fair") and len([p for p in r["prices"].values() if p]) >= 3]
    for r in rows:
        r["ts"] = datetime.fromisoformat(r["ts"])
        r["prices"] = {k: float(v) for k, v in r["prices"].items() if v}
        r["basis"] = mean(sorted(r["prices"].values())[:3])
    return sorted(rows, key=lambda r: r["ts"])


def database(rows):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[MarketSnapshot.__table__, PlatformPrice.__table__])
    session = sessionmaker(bind=engine)()
    for r in rows:
        s = MarketSnapshot(timestamp=r["ts"], fair_price=r["fair"], premium_percent=r["premium"],
                           collection_mode="scheduled", world_gold_usd=r.get("xau"), usd_irr=r.get("usd"))
        session.add(s)
        session.flush()
        for name, price in r["prices"].items():
            session.add(PlatformPrice(snapshot_id=s.id, platform_name=name, price_irr=price, timestamp=r["ts"]))
    session.commit()
    return session


def replay(rows, session, thresholds):
    from analysis.bubble_position import resolve_decision_valuation, signed_gap
    from analysis.confirmation import resolve_signal_confirmation
    from analysis.push_trigger import resolve_push_thresholds
    from caluclator.signal_state import build_signal_state
    from caluclator.signals import apply_hysteresis

    last_alert, last_alert_at, previous = None, None, None
    for r in rows:
        ts, fair = r["ts"], r["fair"]
        markets = {name: {"price": price, "status": "OK"} for name, price in r["prices"].items()}
        valuation = resolve_decision_valuation(session, r["premium"], thresholds, now=ts)
        confirmation = resolve_signal_confirmation(session, markets, fair, r.get("usd"), False, thresholds, now=ts)
        state = build_signal_state(premium=r["premium"], fair_price=fair, lowest_price=min(r["prices"].values()),
                                   markets=markets, previous_premium=previous, thresholds=thresholds,
                                   last_alert=last_alert, last_alert_at=last_alert_at,
                                   valuation=None if valuation.state == "UNKNOWN" else valuation.state,
                                   confirmation=confirmation)
        confirmed = "WAIT" if state.held_reason else state.candidate_decision
        final = apply_hysteresis(confirmed, last_alert, thresholds, last_alert_at=last_alert_at, now=ts)
        if final in ("BUY", "SELL"):
            last_alert, last_alert_at = final, ts
        level = resolve_push_thresholds(session, now=ts).fire_at
        gap = signed_gap(r["basis"], fair)
        r.update(valuation=valuation.state, candidate=state.candidate_decision, held=state.held_reason,
                 final=final, gap=gap, deep=bool(level is not None and gap is not None and gap < 0 and abs(gap) >= level))
        previous = r["premium"]


def after(rows, i, hours):
    target = rows[i]["ts"] + timedelta(hours=hours)
    for j in range(i + 1, len(rows)):
        if rows[j]["ts"] >= target:
            return j if rows[j]["ts"] - target <= timedelta(hours=GAP_HOURS) else None
    return None


def starts(rows, inside):
    out, last = [], None
    for i, r in enumerate(rows):
        if inside(r) and (i == 0 or not inside(rows[i - 1])) and (last is None or r["ts"] - last >= timedelta(hours=GAP_HOURS)):
            out.append(i)
            last = r["ts"]
    return out


def change(rows, i, hours):
    j = after(rows, i, hours)
    return None if j is None else (rows[j]["basis"] / rows[i]["basis"] - 1) * 100


def describe(label, values, control):
    values = [v for v in values if v is not None]
    if not values:
        return f"  {label:<14} n=0"
    return (f"  {label:<14} n={len(values):>3}  mean {mean(values):+.2f}%  median {median(values):+.2f}%  "
            f"(control mean {mean(control):+.2f}%)")


def main():
    config = json.load(open(os.path.join(HERE, "..", "config", "config.json"), encoding="utf-8"))
    rows = load()
    session = database(rows)
    replay(rows, session, config["thresholds"])
    print(f"{len(rows)} readings {rows[0]['ts']:%Y-%m-%d} .. {rows[-1]['ts']:%Y-%m-%d}")
    for key in ("valuation", "candidate", "final"):
        counts = {}
        for r in rows:
            counts[r[key]] = counts.get(r[key], 0) + 1
        print(f"  {key:<10} {dict(sorted(counts.items()))}")
    held = [r["held"] for r in rows if r["candidate"] == "BUY" and r["held"]]
    print(f"  BUY candidates held by the confirmation: {len(held)} of {sum(r['candidate'] == 'BUY' for r in rows)}")
    reasons = {}
    for h in held:
        key = h.split(";")[0][:70]
        reasons[key] = reasons.get(key, 0) + 1
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:4]:
        print(f"      {v:>3}  {k}")

    rules = {"candidate BUY": lambda r: r["candidate"] == "BUY", "final BUY": lambda r: r["final"] == "BUY",
             "deep zone": lambda r: r["deep"]}
    verdicts = {}
    for hours in HORIZONS:
        control = [c for c in (change(rows, i, hours) for i in range(len(rows))) if c is not None]
        print(f"\n+{hours}h basis change after the first reading of each episode")
        print(describe("every reading", control, control))
        for label, inside in rules.items():
            values = [change(rows, i, hours) for i in starts(rows, inside)]
            print(describe(label, values, control))
            if hours == 24:
                values = [v for v in values if v is not None]
                if len(values) < MIN_EPISODES:
                    verdicts[label] = f"INSUFFICIENT ({len(values)} episodes)"
                elif mean(values) - mean(control) >= EDGE_PP:
                    verdicts[label] = f"PICKS BETTER MOMENTS (+{mean(values) - mean(control):.2f} pp, {len(values)} episodes)"
                else:
                    verdicts[label] = f"NO EDGE ({mean(values) - mean(control):+.2f} pp, {len(values)} episodes)"

    # the scorecard's own rule, on every reading with a +24h reading
    hits = {"engine (final)": [0, 0], "always-BUY": [0, 0], "always-WAIT": [0, 0]}
    for i, r in enumerate(rows):
        j = after(rows, i, 24)
        if j is None:
            continue
        shrank = abs(rows[j]["gap"]) - abs(r["gap"])
        if abs(shrank) < 0.05:
            continue
        for label, decision in (("engine (final)", r["final"]), ("always-BUY", "BUY"), ("always-WAIT", "WAIT")):
            right = (shrank < 0) if decision == "BUY" else (shrank > 0)
            hits[label][0] += right
            hits[label][1] += 1
    print("\nthe scorecard's rule at +24h (BUY right when the discount shrank, WAIT right when it grew)")
    for label, (right, n) in hits.items():
        print(f"  {label:<15} {right}/{n} = {right / n:.1%}" if n else f"  {label:<15} n=0")

    # the cost of following the engine: wait from a day's first WAIT to its next final BUY
    from timeutil import local_date
    costs, censored, seen = [], 0, set()
    for i, r in enumerate(rows):
        day = local_date(r["ts"])
        if day in seen or r["final"] != "WAIT":
            continue
        seen.add(day)
        j = next((k for k in range(i + 1, len(rows)) if rows[k]["final"] == "BUY"), None)
        if j is None:
            censored += 1
            continue
        costs.append(((rows[j]["basis"] / r["basis"] - 1) * 100, (rows[j]["ts"] - r["ts"]).total_seconds() / 86400))
    if costs:
        paid = [c for c, _ in costs]
        print(f"\nwaiting for the engine's next BUY, from each day's first WAIT ({len(costs)} days, {censored} censored):")
        print(f"  paid {mean(paid):+.2f}% on average (median {median(paid):+.2f}%), after {median(d for _, d in costs):.1f} days "
              f"(median); cheaper than buying at once on {sum(c < 0 for c in paid)} of {len(paid)} days")

    print("\nverdicts (+24h, decided before the run):")
    for label, verdict in verdicts.items():
        print(f"  {label:<14} {verdict}")


if __name__ == "__main__":
    main()
