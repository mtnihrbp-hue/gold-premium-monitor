"""The central bank's interventions: what the dollar and 18K did 1 to 20 trading days after (SP-D,
SP_D_HANDOFF.md section 41; the owner, 2026-10-16: "when the CBI intervenes, like past week, the dollar
loosens and gold prices drop").

rd_news_labels.py measured 1 and 3 days and found the dollar still rising (37.11). The owner's claim is
about what follows over a week or two: on 2026-09-30 the bank announced $2 billion of banknotes; the dollar
rose 5% in the next three trading days, then fell 4% from 10-06 to 10-13. So the horizon is widened here.

Rules, fixed before the run:
- Events, two definitions, each counted by episodes (a start 7 calendar days or more after the last):
    A  the AI model's label cbi_fx_intervention = true (research/data/news_days.jsonl; 152 of 357 days
       labelled when written, more as the labelling completes)
    B  a channel post whose first line names the central bank or the exchange centre (بانک مرکزی,
       مرکز مبادله) with a supply verb (عرضه, تزریق, فروش) and a currency (ارز, دلار, اسکناس, حواله),
       and no foreign central bank (ژاپن, آمریکا, فدرال, اروپا, چین, ترکیه, روسیه), 2025-10-15 to
       2026-10-15 (research/data/telegram)
- Moves: tgju's dollar (price_dollar_rl) and 18K (geram18), from the last close before the event's day
  to the close h trading days on or after it, h = 1, 3, 5, 10, 20. Control: every calendar day of the
  same span as an event.
- Reported: per definition and horizon, the episodes, the mean and median move, the share that fell,
  against the control.
- Verdict, decided now, on definition B (A as a cross-check): "the dollar falls after an intervention"
  at horizon h when the episodes' mean move is at least 1 pp below the control's, and it fell in at least
  60% of at least 6 episodes. Otherwise not shown at that horizon.

Run: python research/rd_cbi_horizons.py   (reads tgju from the workstation directly)
"""

import glob
import gzip
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from statistics import mean, median

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rd_news_events import moves, series  # noqa: E402

HORIZONS = (1, 3, 5, 10, 20)
GAP_DAYS = 7
TEHRAN = timedelta(hours=3, minutes=30)
BANK = re.compile(r"بانک مرکزی|مرکز مبادله")
SUPPLY = re.compile(r"عرضه|تزریق|فروش")
CURRENCY = re.compile(r"ارز|دلار|اسکناس|حواله")
FOREIGN = re.compile(r"ژاپن|آمریکا|فدرال|اروپا|چین|ترکیه|روسیه")


def episodes(days):
    out, last = [], None
    for d in sorted(days):
        if last is None or (d - last).days >= GAP_DAYS:
            out.append(d)
            last = d
    return out


def events_a():
    path = os.path.join(HERE, "data", "news_days.jsonl")
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    days = [date.fromisoformat(r["day"]) for r in rows if isinstance(r.get("labels"), dict)
            and r["labels"].get("cbi_fx_intervention") is True]
    span = (date.fromisoformat(min(r["day"] for r in rows)), date.fromisoformat(max(r["day"] for r in rows)))
    return episodes(days), span


def events_b():
    days, first, last, samples = set(), None, None, {}
    for p in glob.glob(os.path.join(HERE, "data", "telegram", "*.jsonl.gz")):
        for line in gzip.open(p, "rt", encoding="utf-8"):
            post = json.loads(line)
            day = (datetime.fromisoformat(post["at"]) + TEHRAN).date()
            first, last = min(first or day, day), max(last or day, day)
            head = (post.get("text") or "").strip().split("\n")[0]
            if BANK.search(head) and SUPPLY.search(head) and CURRENCY.search(head) and not FOREIGN.search(head):
                days.add(day)
                samples.setdefault(day, " ".join(head.split())[:100])
    eps = episodes(days)
    return eps, (first, last), {d: samples[d] for d in eps}


def report(label, eps, span, usd, gold):
    print(f"\n=== {label}: {len(eps)} episodes, {span[0]} .. {span[1]}")
    control_days = [span[0] + timedelta(days=k) for k in range((span[1] - span[0]).days + 1)]
    verdict = {}
    for name, prices in (("dollar", usd), ("18K", gold)):
        for h in HORIZONS:
            ev = [m for m in (moves(prices, d, h) for d in eps) if m is not None]
            ctrl = [m for m in (moves(prices, d, h) for d in control_days) if m is not None]
            if not ev:
                continue
            fell = sum(m < 0 for m in ev) / len(ev)
            print(f"  {name:<6} +{h:>2}d  n={len(ev):>2}  mean {mean(ev):+.2f}%  median {median(ev):+.2f}%  fell {fell:.0%}"
                  f"   (control mean {mean(ctrl):+.2f}%, fell {sum(m < 0 for m in ctrl) / len(ctrl):.0%})")
            if name == "dollar":
                verdict[h] = (len(ev) >= 6 and mean(ev) <= mean(ctrl) - 1 and fell >= 0.6)
    return verdict


def main():
    usd, gold = series("price_dollar_rl"), series("geram18")
    a, span_a = events_a()
    b, span_b, samples = events_b()
    report("A, the AI model's intervention days", a, span_a, usd, gold)
    verdict = report("B, the channels' supply headlines", b, span_b, usd, gold)
    print("\n  B's episodes:")
    for d in b:
        print(f"    {d}  {samples[d]}")
    print("\nverdict (definition B, decided before the run):")
    for h in HORIZONS:
        print(f"  +{h:>2}d  {'THE DOLLAR FALLS AFTER AN INTERVENTION' if verdict.get(h) else 'not shown'}")


if __name__ == "__main__":
    main()
