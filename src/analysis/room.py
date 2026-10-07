"""The room: the PAPER front office's posture, read from the evidence (SP-D, SP_D_HANDOFF.md
sections 17-27).

The owner's room (2026-10-05): "if the trend is bullish, all out to gold; if sideways, ... sell some
gold into fixed income and keep the rest, and keep a sharp eye to rebuy the sold gold back." Read
from the chart alone the phase arrives late (section 26: the exits sell low, the returns buy high);
read from the evidence it comes earlier, so the room's members decide the posture:

  ALL_GOLD    every gram in gold -- the default
  SWING_OUT   40% of the grams sold into fixed income (Afran), 60% kept in gold

Members, each with a lean every day (+1 gold, -1 fixed income, 0 none), all causal, defined as in
research/rd_committee_2y.py; a z-score leans beyond +/-0.5 against its own last 500 days:

  brake           2.0   the quant engine's growth-optimal share under 0.9 (a storm) -> -1, else +1
  market state    1.5   sideways (the 60-day efficiency ratio under a random walk's) without a new
                        60-day high -> -1; a new 60-day closing high -> +1
  fair gap        1.5   18K's gap to world gold x the dollar against its 250-day median: a deeper
                        discount -> +1
  real dollar     1.5   the dollar against the cost of money (fixed income), against its 500 days:
                        behind -> +1 (a devaluation pending)
  dollar 20d      1.0   the dollar's last 20 days: rising -> +1
  world gold 60d  0.5   world gold's last 60 days: rising -> +1
  chartist        1.0   caluclator/chartist.py's view: over +0.25 -> +1, under -0.25 -> -1
  money flow      0.5   the gold funds' buyer power -- individuals' value per buyer over value per
                        seller, summed over the funds, its last 20 trading days' mean: stronger
                        buyers -> +1. TSETMC's client types, which only an Iranian address can read:
                        src/seed/gold_fund_flows.json to 2026-10-03, then the owner's phone (iran_node,
                        sections 30, 33); a day counts when FLOW_MIN_FUNDS of the 19 funds have it

The committee's view moves every day: it turns to fixed income when the members leaning that way
hold 60% of the weight of those with a view (two at least), and back at 30% or less. The posture
follows it only on a review day, every REVIEW_EVERY trading days from the account's start, with the
stock index as the sharp eye (sections 24, 27): no sale while its last 20 days lean to gold, and
while out, back to gold early on the first day they turn to gold after the sale -- a standing rise
does not buy back the morning after a sale. Replayed (section 27), without money flow: median +4.0
to +5.7% against holding per two years, ahead in 83-100% of the two-year windows since 2020, worst
-3.3% (-11.3% from 2018), seven trades in the last two years. With money flow (section 33): +5.0 to
+9.0%, ahead in 83-100%, worst -3.7% (-10.2% from 2018).
"""

from bisect import bisect_right

import numpy as np

WEIGHTS = {"brake": 2.0, "market state": 1.5, "fair gap": 1.5, "real dollar": 1.5, "dollar 20d": 1.0,
           "world gold 60d": 0.5, "chartist": 1.0, "money flow": 0.5}
FLOW_DAYS = 20            # the money-flow member's mean, in the funds' trading days
FLOW_MIN_FUNDS = 15       # a day from the phone counts when this many of the 19 funds have it
LEAVE, BACK = 0.60, 0.30
REVIEW_EVERY = 10
SWING = 0.40
Z_WINDOW = 500
ER_DAYS = 60
BRAKE_BELOW = 0.9
ALL_GOLD, SWING_OUT = "ALL_GOLD", "SWING_OUT"

# the members' reasons, in plain words, for the messages (wording: "heavily discounted", never cheap)
WHY = {
    ("brake", -1): "the market is stormy", ("brake", 1): "the market is calm",
    ("market state", -1): "the market is moving sideways", ("market state", 1): "18K made a new 60-day high",
    ("fair gap", -1): "18K is less discounted than usual against world gold and the dollar",
    ("fair gap", 1): "18K is more discounted than usual against world gold and the dollar",
    ("real dollar", -1): "the dollar is ahead of the cost of money",
    ("real dollar", 1): "the dollar is behind the cost of money",
    ("dollar 20d", -1): "the dollar decreased over 20 days", ("dollar 20d", 1): "the dollar increased over 20 days",
    ("world gold 60d", -1): "world gold decreased over 60 days", ("world gold 60d", 1): "world gold increased over 60 days",
    ("chartist", -1): "the chart turned down", ("chartist", 1): "the chart points up",
    ("money flow", -1): "sellers in the gold funds are stronger than usual",
    ("money flow", 1): "buyers in the gold funds are stronger than usual",
}


def aligned(dates, series_dates, series_values, max_gap_days=7):
    """series' last known value on or before each of `dates` (NaN when older than max_gap_days)."""
    out = np.full(len(dates), np.nan)
    for k, x in enumerate(dates):
        j = bisect_right(series_dates, x) - 1
        if j >= 0 and (x - series_dates[j]).days <= max_gap_days:
            out[k] = series_values[j]
    return out


def zscore(s, window=Z_WINDOW):
    s = np.asarray(s, dtype=float)
    out = np.full(len(s), np.nan)
    for i in range(window, len(s)):
        w = s[i - window:i]
        w = w[np.isfinite(w)]
        if len(w) > 100 and np.isfinite(s[i]) and np.std(w) > 0:
            out[i] = (s[i] - np.mean(w)) / np.std(w)
    return out


def against_own(x, window, how="mean"):
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    for i in range(window, len(x)):
        w = x[i - window:i]
        w = w[np.isfinite(w)]
        if len(w) > window * 0.8 and np.isfinite(x[i]):
            out[i] = x[i] - (np.mean(w) if how == "mean" else np.median(w))
    return out


def lean_from_z(z, sign):
    v = np.nan_to_num(np.asarray(z, dtype=float)) * sign
    return np.where(v > 0.5, 1, np.where(v < -0.5, -1, 0))


def back(x, k):
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    out[k:] = x[k:] - x[:-k]
    return out


def efficiency_sideways(close, flat, days=ER_DAYS):
    c = np.asarray(close, dtype=float)
    side = np.zeros(len(c), dtype=bool)
    for i in range(days, len(c)):
        if np.mean(flat[i - days + 1:i + 1]) > 0.3:
            continue
        moves = np.abs(np.diff(c[i - days:i + 1])).sum()
        er = abs(c[i] - c[i - days]) / moves if moves else 0.0
        side[i] = er < 1 / np.sqrt(days)
    return side


def money_flow(dates, flow_days, power):
    """The buyer power's mean over its last FLOW_DAYS trading days, on `dates`: NaN where the funds'
    last day is a week or more old (as rd_committee_2y.py builds the member)."""
    power = np.asarray(power, dtype=float)
    power20 = np.array([np.mean(power[max(0, j - FLOW_DAYS + 1):j + 1]) for j in range(len(power))])
    return aligned(dates, flow_days, power20, max_gap_days=6)


def member_leans(high, low, close, usd, xau, fi_level, tedpix, f_star, flat, chartist=None, from_index=0,
                 flow=None):
    """{member: lean array} for every day, and the stock index's lean (the early return).
    `from_index`: the chartist reads only from this day on (it is the slow member). `flow`: the
    money-flow member's input on the same days (money_flow); without it the member has no view."""
    c = np.asarray(close, dtype=float)
    n = len(c)
    lc = np.log(c)
    high60 = np.array([i >= 60 and c[i] >= c[i - 59:i + 1].max() for i in range(n)])
    side = efficiency_sideways(c, flat)
    gap = against_own(np.log(c / (np.asarray(xau) * np.asarray(usd) / 31.1035 * 0.75)), 250, "median")
    real = against_own(np.log(np.asarray(usd)) - np.log(np.asarray(fi_level)), 500)
    leans = {
        "brake": np.where(np.nan_to_num(np.asarray(f_star, dtype=float), nan=1.0) < BRAKE_BELOW, -1, 1),
        "market state": np.where(high60, 1, np.where(side, -1, 0)),
        "fair gap": lean_from_z(zscore(gap), -1),
        "real dollar": lean_from_z(zscore(real), -1),
        "dollar 20d": lean_from_z(zscore(back(np.log(np.asarray(usd)), 20)), +1),
        "world gold 60d": lean_from_z(zscore(back(np.log(np.asarray(xau)), 60)), +1),
        "chartist": np.zeros(n, dtype=int),
        "money flow": (lean_from_z(zscore(flow), +1) if flow is not None else np.zeros(n, dtype=int)),
    }
    if chartist is not None:
        for i in range(max(from_index, 0), n):
            r = chartist.read(i)
            s = r["score"] if r["structure"] else 0.0
            leans["chartist"][i] = 1 if s > 0.25 else -1 if s < -0.25 else 0
    stocks = lean_from_z(zscore(back(np.log(np.asarray(tedpix, dtype=float)), 20)), +1)
    return leans, stocks


def share_for_fixed_income(leans, i, weights=WEIGHTS):
    opinion = {m: int(leans[m][i]) for m in weights if weights[m] > 0 and int(leans[m][i]) != 0}
    if len(opinion) < 2:
        return 0.0, opinion
    against = sum(weights[m] for m, v in opinion.items() if v == -1)
    return against / sum(weights[m] for m in opinion), opinion


def replay(leans, stocks, start, end, weights=WEIGHTS, every=REVIEW_EVERY):
    """The committee's daily view and the posture from day `start` (the account's first day, all in
    gold) to `end`. Returns a list of dicts, one per day: inner (the committee leaning to fixed
    income), review (a review day), posture, share, early (the stock index brought it back)."""
    out, inner, held, exit_stocks = [], False, False, 0
    for i in range(start, end + 1):
        share, _ = share_for_fixed_income(leans, i, weights)
        if not inner and share >= LEAVE:
            inner = True
        elif inner and share <= BACK:
            inner = False
        review = (i - start) % every == 0
        early = vetoed = False
        s_i = int(stocks[i])
        if review:
            want = inner
            if want and not held and s_i == 1:          # no sale while the stock index leans to gold
                want, vetoed = False, True
            if want and not held:
                exit_stocks = s_i
            held = want
        elif held:
            if s_i == 1 and exit_stocks != 1:           # a new turn up after the sale: back early
                held, early = False, True
            exit_stocks = s_i if s_i != 1 else exit_stocks
        out.append({"inner": inner, "review": review, "posture": SWING_OUT if held else ALL_GOLD,
                    "share": share, "early": early, "vetoed": vetoed})
    return out


def forecast_band(close, mu, f_window=1500, horizon=20):
    """The next `horizon` trading days' range from 18K's own past moves (filtered historical
    simulation, section 18): (low80, high80, low95, high95, centre) as prices, or None."""
    c = np.asarray(close, dtype=float)
    lc = np.log(c)
    r = np.diff(lc)
    if len(r) < f_window // 2:
        return None
    var = np.zeros(len(c))
    var[0] = np.var(r[:60])
    for k in range(1, len(c)):
        var[k] = 0.94 * var[k - 1] + 0.06 * r[k - 1] ** 2
    sig = np.sqrt(var)
    mu = np.nan_to_num(np.asarray(mu, dtype=float))
    i = len(c) - 1
    z = []
    for t in range(max(0, i - horizon - f_window), i - horizon):
        if sig[t] > 0:
            z.append((lc[t + horizon] - lc[t] - mu[t] * horizon) / (sig[t] * np.sqrt(horizon)))
    if len(z) < 250:
        return None
    q = np.quantile(z, [0.10, 0.90, 0.025, 0.975])
    mid = lc[i] + mu[i] * horizon
    s = sig[i] * np.sqrt(horizon)
    lo80, hi80, lo95, hi95 = (float(np.exp(mid + k * s)) for k in q)
    return lo80, hi80, lo95, hi95, float(np.exp(mid))


def reasons(opinion, posture, limit=2):
    """The members' reasons for the posture, in plain words, the heaviest first."""
    side = -1 if posture == SWING_OUT else 1
    picked = sorted((m for m, v in opinion.items() if v == side), key=lambda m: -WEIGHTS.get(m, 0))
    return [WHY[(m, side)] for m in picked[:limit] if (m, side) in WHY]
