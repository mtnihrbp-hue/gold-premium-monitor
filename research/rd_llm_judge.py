"""The LLM as the committee's chair, replayed on the last two years (SP-D, 2026-10-05).

Why it can be replayed here: openai/gpt-oss-120b's knowledge ends in mid-2024 (its model
card), and the window starts in October 2024. The briefs also carry no dates and no price
levels -- 18K, the dollar and world gold appear as indexes (today = 100) and changes -- so
nothing in them names the period.

    python rd_llm_judge.py build   -> data/llm_briefs.json: one brief every 5 trading days
    (on GitHub's runner: probe/llm_judge.py calls Groq in order, feeding back its position)
    python rd_llm_judge.py score   -> reads data/llm_decisions.json, replays the contract

The brief: the contract (the 40% swing, gold or fixed income, for the next 5 trading days),
the current position (filled in on the runner), 18K's path and moves, fixed income's
yield, the dollar, world gold, the fair gap, the gold funds' buyer power, the chartist's
reading, and each member's lean with its record so far (when it said fixed income, how
often fixed income won, against the base rate), all known on that day.
"""
import json
import os
import sys

import numpy as np

import rd_committee_2y as R
from rd_rebuy import SIG, X20, c, d, n, usd, ons

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "llm_briefs.json")
DEC = os.path.join(HERE, "data", "llm_decisions.json")
EVERY = 5
idx = [i for i in range(n) if R.START <= d[i] <= R.END]
dates = idx[::EVERY]

SYSTEM = ("You are the chair of an investment committee for a paper account in Iranian 18K gold, priced in toman. "
          "You weigh the evidence like a senior discretionary trader and decide. You never invent numbers: use only "
          "the figures given. Answer with JSON only.")


def pct(a, b):
    return (a / b - 1) * 100


def record(m, i):
    """(share of the member's fixed-income calls that fixed income won, share of its gold calls
    that gold won, days of each) over the 500 trading days whose 20-day outcome is known at i."""
    sel = [k for k in range(max(0, i - 520), i - 20) if np.isfinite(X20[k])]
    fi = [X20[k] < 0 for k in sel if R.LEAN[m][k] == -1]
    go = [X20[k] > 0 for k in sel if R.LEAN[m][k] == 1]
    base = np.mean([X20[k] > 0 for k in sel]) * 100 if sel else np.nan
    return (np.mean(fi) * 100 if fi else None, len(fi), np.mean(go) * 100 if go else None, len(go), base)


MEANING = {
    "brake": "the volatility brake (growth-optimal share under 0.9 = too stormy)",
    "market state": "sideways or trending (sideways and no new 60-day high = fixed income; a new 60-day high = gold)",
    "fair gap": "18K's gap to fair value against its usual (deeper discount = gold)",
    "real dollar": "the dollar against the cost of money (behind = gold, a devaluation pending)",
    "dollar 20d": "the dollar's last 20 days (rising = gold)",
    "world gold 60d": "world gold's last 60 days (rising = gold)",
    "money flow": "the gold funds' buyer power (individuals buying in larger tickets than sellers = gold)",
    "chartist": "the chart reader's overall view",
}


def brief(i, k):
    ix = lambda a, j: a[j] / a[i] * 100
    weekly = [f"{ix(c, i - 5 * w):.0f}" for w in range(12, -1, -1)]
    daily = [f"{ix(c, i - w):.1f}" for w in range(9, -1, -1)]
    hi52 = c[max(0, i - 249):i + 1].max()
    ret = np.diff(np.log(c[max(0, i - 260):i + 1]))
    vol20 = np.std(ret[-20:]) * np.sqrt(250) * 100
    vols = [np.std(ret[j - 20:j]) for j in range(20, len(ret) + 1)]
    vol_rank = np.mean(np.array(vols) <= np.std(ret[-20:])) * 100
    fi60 = ((R.af_level[i] / R.af_level[i - 60]) ** (250 / 60) - 1) * 100
    rd = R.chart.read(i)
    chn = rd["channel"]
    box = rd.get("box")
    fair = SIG["fair gap (low = discount)"][i] * 100
    lines = [
        f"Decision {k + 1} of {len(dates)}. No dates or price levels are given: prices are indexes, today = 100.",
        "THE CONTRACT: 60% of the grams always stay in gold. You decide where the other 40% (the swing) sits for the next "
        "5 trading days: GOLD or FIXED_INCOME (an Iranian fixed-income fund). Each move between them costs about 0.4%. "
        "The goal: end every quarter with more money than holding all the grams in gold.",
        "THE SWING IS NOW IN: {POSITION}.",
        f"18K, weekly closes, oldest first: {', '.join(weekly)}. Last 10 days: {', '.join(daily)}.",
        f"18K moved {pct(c[i], c[i - 20]):+.1f}% in 20 trading days, {pct(c[i], c[i - 60]):+.1f}% in 60, {pct(c[i], c[i - 120]):+.1f}% "
        f"in 120; it is {pct(c[i], hi52):+.1f}% from its 52-week high. Volatility {vol20:.0f}% a year, higher than {vol_rank:.0f}% "
        f"of the last year's readings.",
        f"Fixed income paid {fi60:.0f}% a year over the last 60 days.",
        f"Dollar (free market): {pct(usd[i], usd[i - 20]):+.1f}% in 20 days, {pct(usd[i], usd[i - 60]):+.1f}% in 60. "
        f"World gold: {pct(ons[i], ons[i - 20]):+.1f}% in 20 days, {pct(ons[i], ons[i - 60]):+.1f}% in 60.",
        f"18K against fair value (world gold x dollar): {fair:+.1f} points from its usual gap (negative = more discounted than usual).",
        f"Chart: structure {rd['structure']}, phase {rd['phase']}, patterns: {', '.join(rd['patterns']) or 'none'}; channel "
        f"{chn['slope_pct_day']:+.2f}% a day over {chn['days']} days, the price at {chn['position']:.2f} of it (0 = bottom, 1 = top)"
        + (f"; sideways box {box[0] / c[i] * 100:.0f}-{box[1] / c[i] * 100:.0f}." if box else "."),
        "THE COMMITTEE (each member's lean today; its record over the last two years known today):",
    ]
    base = None
    for m in R.MEMBERS:
        v = R.LEAN[m][i]
        fi, nfi, go, ngo, base = record(m, i)
        rec = []
        if fi is not None:
            rec.append(f"when it said fixed income, fixed income won {fi:.0f}% of {nfi} days")
        if go is not None:
            rec.append(f"when it said gold, gold won {go:.0f}% of {ngo} days")
        lines.append(f"- {m} ({MEANING[m]}): {'GOLD' if v == 1 else 'FIXED_INCOME' if v == -1 else 'no view'}; "
                     + ("; ".join(rec) or "no record yet"))
    lines.append(f"Over the same two years gold beat fixed income over 20 days on {base:.0f}% of days.")
    lines.append('Answer: {"swing": "GOLD" or "FIXED_INCOME", "confidence": 0 to 1, "reasons": [up to 3 short reasons], '
                 '"would_change_mind": "one sentence"}')
    return "\n".join(lines)


def build():
    out = [{"k": k, "i": int(i), "brief": brief(i, k)} for k, i in enumerate(dates)]
    json.dump({"system": SYSTEM, "every": EVERY, "briefs": out}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sizes = [len(b["brief"]) for b in out]
    print(f"{len(out)} briefs -> {OUT}; {np.mean(sizes):.0f} characters on average (about {np.mean(sizes) / 3.5:.0f} tokens)")
    print("\n--- the first brief ---\n" + out[0]["brief"])


def score():
    D = json.load(open(DEC, encoding="utf-8"))
    by_i = {int(x["i"]): x for x in D["decisions"] if x.get("swing") in ("GOLD", "FIXED_INCOME")}
    print(f"{len(by_i)} valid decisions of {len(dates)}; model {D.get('model')}")

    def llm_factory(window):
        state = {"out": False}

        def f(i):
            if i in by_i:
                state["out"] = by_i[i]["swing"] == "FIXED_INCOME"
            return state["out"]
        return f

    E = R.evaluate(R.START, R.END, extra=[("LLM chair (weekly)", llm_factory)])
    res = E["res"]
    hold = res["hold (the bar)"]["end"]
    print("the last two years, the same contract (ranked)")
    for name, rs in sorted(res.items(), key=lambda kv: -kv[1]["end"]):
        print(f"   {name:36} {rs['end'] / 1e7:7.1f}M  {(rs['end'] / hold - 1) * 100:+6.1f}%  trades {rs['trades']:3}  days out "
              f"{rs['out_days']:4}  exits that beat staying {rs['good_exits']}/{rs['exits']}")
    calls = [(x["swing"], X20[int(x["i"])]) for x in by_i.values() if np.isfinite(X20[int(x["i"])])]
    g = [v > 0 for s_, v in calls if s_ == "GOLD"]
    f_ = [v < 0 for s_, v in calls if s_ == "FIXED_INCOME"]
    print(f"   the chair's calls: gold {len(g)} times (gold won {np.mean(g) * 100 if g else np.nan:.0f}% over the next 20 days), "
          f"fixed income {len(f_)} times (fixed income won {np.mean(f_) * 100 if f_ else np.nan:.0f}%)")
    conf = [x.get("confidence") for x in by_i.values() if isinstance(x.get("confidence"), (int, float))]
    print(f"   confidence: median {np.median(conf):.2f}" if conf else "")
    for x in [v for v in by_i.values() if v["swing"] == "FIXED_INCOME"][:8]:
        print(f"   {R.rows[int(x['i'])]['jdate']} FIXED_INCOME ({x.get('confidence')}): {'; '.join(x.get('reasons', []))[:220]}")


if __name__ == "__main__":
    {"build": build, "score": score}[sys.argv[1]]()
