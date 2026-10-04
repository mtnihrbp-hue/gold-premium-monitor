"""The front office as the back office's convergent decision (SP-D, 2026-10-04).

The owner: "the front office can be a convergent decision made at back office, including
the llm. Explore the idea." And the contract: buy 5 grams, sell 2, hold 3; the 2 grams' cash
goes straight into fixed income; when the trader buys, it pulls the money out and adds to
the 3 grams.

rd_rebuy.py found that what says gold will beat fixed income changes with the era: the
dollar's own momentum in 2016-2020, the dollar behind the cost of money and 18K's discount
to fair value in 2021-2026. A committee that weighs each member by its record so far can
follow that. Three ways to converge, all walk-forward (weights at day i from outcomes known
by day i: the 60-day outcomes of days up to i - 60, over the 500 days before that):

  VOTE     each member's z-score with the sign of its record, averaged (equal weights)
  RECORD   the same, weighted by each member's rank correlation on record (zero under 0.05)
  RIDGE    a ridge regression of gold-over-fixed-income on all members, a forecast in %

Then the contract, with Daric's 0.30% and fixed income's 0.10% round trips: a core in gold
and a swing that sits in gold or in fixed income by the committee's sign; the cash moves
"directly" (the owner's contract, lag 0) or in 2 trading days each way (lag 2).

The LLM cannot be replayed (it has read the history); it joins live as one more member,
weighed by its own record the same way.
"""
from datetime import date

import numpy as np
from scipy.stats import rankdata

from rd_rebuy import SIG, X60, c, d, fi_log, n, rows, side

FIRST = next(i for i in range(n) if d[i] >= date(2016, 1, 1))
WINDOW, H, STEP = 500, 60, 5
names = list(SIG)
Z = np.full((n, len(names)), np.nan)
for k, nm in enumerate(names):
    s = SIG[nm]
    for i in range(FIRST, n):
        w = s[max(0, i - WINDOW):i]
        w = w[np.isfinite(w)]
        if len(w) > 100 and np.isfinite(s[i]) and np.std(w) > 0:
            Z[i, k] = (s[i] - np.mean(w)) / np.std(w)
Z[:, names.index("sideways age")] = np.nan_to_num(Z[:, names.index("sideways age")], nan=-1.0)  # 0 days = not sideways


def rank_ic(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 150:
        return np.nan
    return np.corrcoef(rankdata(a[ok]), rankdata(b[ok]))[0, 1]


VOTE, RECORD, RIDGE = (np.full(n, np.nan) for _ in range(3))
weights_log = []
for i in range(FIRST + WINDOW + H, n, STEP):
    lo, hi = i - H - WINDOW, i - H          # outcomes known by day i
    ics = np.array([rank_ic(Z[lo:hi, k], X60[lo:hi]) for k in range(len(names))])
    ics = np.nan_to_num(ics)
    Xw, yw = Z[lo:hi], X60[lo:hi]
    ok = np.all(np.isfinite(Xw), axis=1) & np.isfinite(yw)
    beta = None
    if ok.sum() > 200:
        A = np.column_stack([np.ones(ok.sum()), Xw[ok]])
        lam = 50.0 * np.eye(A.shape[1])
        lam[0, 0] = 0
        beta = np.linalg.solve(A.T @ A + lam, A.T @ yw[ok])
    weights_log.append((i, ics))
    for j in range(i, min(n, i + STEP)):
        z = np.nan_to_num(Z[j])
        VOTE[j] = np.mean(np.sign(ics) * z)
        w = np.where(np.abs(ics) >= 0.05, ics, 0)
        RECORD[j] = (w @ z) / max(np.abs(w).sum(), 1e-9)
        if beta is not None:
            RIDGE[j] = beta[0] + beta[1:] @ z

print("1. THE COMMITTEE'S FORECAST against what happened (gold over fixed income, next 60 days)")
print("   year   VOTE: IC  right sign | RECORD: IC  right sign | RIDGE: IC  right sign  | sideways days")
for y in range(2018, 2027):
    sel = np.array([x.year == y for x in d]) & np.isfinite(X60)
    cells = []
    for f in (VOTE, RECORD, RIDGE):
        ok = sel & np.isfinite(f)
        if ok.sum() < 40:
            cells.append("     -        -     ")
            continue
        right = np.mean(np.sign(f[ok]) == np.sign(X60[ok])) * 100
        cells.append(f"{rank_ic(f[ok], X60[ok]):+6.2f}  {right:5.0f}%   ")
    print(f"   {y}  " + "| ".join(cells) + f"| {np.mean(side[sel]) * 100:3.0f}%")
for label, lo, hi in (("2018-2023", date(2018, 1, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2026, 12, 31))):
    sel = np.array([lo <= x <= hi for x in d]) & np.isfinite(X60)
    print(f"   {label} " + " | ".join(
        f"{nm} IC {rank_ic(f[sel], X60[sel]):+.2f}, sign right {np.mean(np.sign(f[sel & np.isfinite(f)]) == np.sign(X60[sel & np.isfinite(f)])) * 100:.0f}%"
        for nm, f in (("VOTE", VOTE), ("RECORD", RECORD), ("RIDGE", RIDGE))))

print("\n   the weights RECORD gave each member (rank correlation on record), at the start of each year")
seen = set()
for i, ics in weights_log:
    if d[i].year not in seen:
        seen.add(d[i].year)
        print(f"   {d[i]}  " + "  ".join(f"{nm.split(' (')[0]} {v:+.2f}" for nm, v in zip(names, ics)))

# 2. the contract ---------------------------------------------------------------------------
fi_ret = np.zeros(n)
fi_ret[1:] = np.expm1(np.diff(fi_log))
fi_ret = np.nan_to_num(fi_ret)
GOLD_HALF, FI_HALF = 0.30 / 200, 0.10 / 200


def simulate(target, lo, hi, lag):
    """target(i) -> gold share after day i. Sales go to fixed income and buys come out of it,
    `lag` trading days each way (the buy fills at the price of the day the money arrives)."""
    idx = [i for i in range(n - 1) if lo <= d[i] <= hi]
    gold, fund, transit, orders = 0.0, 1.0, [], []
    first = True
    for i in idx[:-1]:
        j = i + 1
        fund *= 1 + fi_ret[j]
        buy, sell = c[j] * (1 + GOLD_HALF), c[j] * (1 - GOLD_HALF)
        for q in [x for x in transit if x[0] <= j]:
            fund += q[1] * (1 - FI_HALF)
            transit.remove(q)
        for q in [x for x in orders if x[0] <= j]:
            gold += q[1] / buy
            orders.remove(q)
        value = gold * sell + fund + sum(q[1] for q in transit) + sum(q[1] for q in orders)
        share = (gold * sell + sum(q[1] for q in orders)) / value
        tg = target(i)
        if first or abs(tg - share) > 0.05:
            first = False
            amount = (tg - share) * value
            if amount > 0:
                amount = min(amount, fund)
                fund -= amount
                if lag:
                    orders.append((j + lag, amount * (1 - FI_HALF)))
                else:
                    gold += amount * (1 - FI_HALF) / buy
            elif amount < 0:
                q = min(gold, -amount / sell)
                gold -= q
                if lag:
                    transit.append((j + lag, q * sell))
                else:
                    fund += q * sell * (1 - FI_HALF)
    j = idx[-1]
    return gold * c[j] * (1 - GOLD_HALF) + fund + sum(q[1] for q in transit) + sum(q[1] for q in orders)


def swing(forecast, core):
    return lambda i: 1.0 if not np.isfinite(forecast[i]) else (1.0 if forecast[i] > 0 else core)


SPANS = (("2018-07 -> 2023", date(2018, 7, 1), date(2023, 12, 31)), ("2024-2026", date(2024, 1, 1), date(2026, 12, 31)),
         ("1405: channel and jump", date(2026, 2, 1), date(2026, 12, 31)))
start = d[next(i for i in range(n) if np.isfinite(RIDGE[i]))]
print(f"\n2. THE CONTRACT (the committee forecasts from {start}): end value of 1, against holding gold; lag 0 | lag 2")
for label, lo, hi in SPANS:
    hold = simulate(lambda i: 1.0, lo, hi, 0)
    fi_only = simulate(lambda i: 0.0, lo, hi, 0)
    print(f"   {label}: hold gold x{hold:.2f}, all in fixed income x{fi_only:.2f}")
    for name, tg in (("core 60% + swing always in fixed income", lambda i: 0.6),
                     ("core 60% + swing by VOTE", swing(VOTE, 0.6)), ("core 60% + swing by RECORD", swing(RECORD, 0.6)),
                     ("core 60% + swing by RIDGE", swing(RIDGE, 0.6)), ("all or nothing by RIDGE", swing(RIDGE, 0.0)),
                     ("all or nothing by RECORD", swing(RECORD, 0.0))):
        a, b = simulate(tg, lo, hi, 0), simulate(tg, lo, hi, 2)
        print(f"      {name:42} x{a:6.2f} ({(a / hold - 1) * 100:+6.1f}%) | x{b:6.2f} ({(b / hold - 1) * 100:+6.1f}%)")

print("\n3. 1405 CHANNEL: what the committee said (every 10th trading day)")
for i in range(n):
    if date(2026, 2, 1) <= d[i] and i % 10 == 0:
        print(f"   {rows[i]['jdate']} {c[i] / 1e7:5.1f}M {'S' if side[i] else '.'}  VOTE {VOTE[i]:+.2f}  RECORD {RECORD[i]:+.2f}"
              f"  RIDGE {RIDGE[i]:+5.1f}%  -> {'gold' if RIDGE[i] > 0 else 'fixed income'}"
              + (f"   (gold over fixed income in the next 60 days: {X60[i]:+.0f}%)" if np.isfinite(X60[i]) else ""))

# 4. leaving gold is the expensive mistake: sell the swing only on consensus, return on doubt
print("\n4. CONSENSUS TO LEAVE, DOUBT TO RETURN: the swing (40%) goes to fixed income only when at least")
print("   `leave` of the members favour it, and comes back when no more than `back` do; lag 0 | lag 2")
base = {label: np.mean(X60[np.array([lo <= x <= hi for x in d]) & np.isfinite(X60)] > 0) * 100 for label, lo, hi in SPANS}
print("   gold beat fixed income over 60 days on " + ", ".join(f"{v:.0f}% of days in {k}" for k, v in base.items()))
PRIOR = {"real dollar (low = behind)": -1, "real gold (low = behind)": -1, "fair gap (low = discount)": -1,
         "world gold 60 days": +1, "dollar 20 days": +1}
prior_cols = [names.index(k) for k in PRIOR]
prior_sign = np.array(list(PRIOR.values()))
record_sign = np.zeros((n, len(names)))
for i, ics in weights_log:
    record_sign[i:i + STEP] = np.sign(ics)


def against(i, by):
    """How many members favour fixed income on day i (z beyond 0.5 against gold)."""
    if by == "prior":
        z = Z[i, prior_cols] * prior_sign
    else:
        if not record_sign[i].any():
            return None
        z = Z[i] * record_sign[i]
    return int(np.sum(np.nan_to_num(z) < -0.5))


def consensus(by, leave, back):
    state = {"out": False}

    def t(i):
        k = against(i, by)
        if k is None:
            return 1.0
        if not state["out"] and k >= leave:
            state["out"] = True
        elif state["out"] and k <= back:
            state["out"] = False
        return 0.6 if state["out"] else 1.0
    return t


for label, lo, hi in SPANS:
    hold = simulate(lambda i: 1.0, lo, hi, 0)
    print(f"   {label}: hold gold x{hold:.2f}")
    for by, members in (("prior", len(PRIOR)), ("record", len(names))):
        for leave, back in ((3, 1), (4, 1), (members, 2)):
            if leave > members:
                continue
            a, b = simulate(consensus(by, leave, back), lo, hi, 0), simulate(consensus(by, leave, back), lo, hi, 2)
            days_out = np.mean([consensus(by, leave, back)(i) < 1 for i in range(n) if lo <= d[i] <= hi]) * 100
            print(f"      signs by {by:6}, leave on {leave} of {members}, back at {back}: x{a:6.2f} ({(a / hold - 1) * 100:+6.1f}%)"
                  f" | x{b:6.2f} ({(b / hold - 1) * 100:+6.1f}%)   swing out {days_out:.0f}% of days")
