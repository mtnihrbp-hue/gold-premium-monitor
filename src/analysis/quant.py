"""The quant engine: growth-optimal sizing on an estimated drift (SP-D, SP_D_HANDOFF.md
sections 12-13).

The owner's objective -- the most money at the period's end against its start -- over
many periods is maximizing expected log wealth (Kelly / Merton). With cash at 0, no
borrowing and no short selling, the growth-optimal share in gold is

    f* = clip( mu / sigma^2 , 0 , 1 )

and with a round-trip cost c the account does not trade inside a band of half-width
(3/2 c f*^2 (1-f*)^2)^(1/3) around f* (Davis-Norman, small-cost asymptotics).

mu: 18K's drift from its own two-regime model (statsmodels MarkovRegression, switching
mean and variance) on completed daily log returns, filtered forward with parameters
fitted once per quarter (the contract changes rules only at a quarter boundary).
sigma^2: the EWMA (0.94) of squared daily log returns. Its regimes are calm and storm,
both rising, so f* falls below 1 only when swings explode: a volatility brake, which on
2016-2023 beat holding by 13-18% (all of it in 2018's currency crisis) and trailed it by
0.7% on 2024-2026 (research/rd_quant.py, rd_trade_more.py).
"""

import numpy as np

EWMA_LAMBDA = 0.94
MIN_RETURNS = 500


def log_returns(close):
    c = np.asarray(close, dtype=float)
    return np.diff(np.log(c))


def ewma_variance(returns, lam=EWMA_LAMBDA):
    r = np.asarray(returns, dtype=float)
    v = np.var(r[:60])
    for x in r:
        v = lam * v + (1 - lam) * x * x
    return float(v)


def fit_regimes(returns):
    """{"params": [...], "names": [...]} of a two-regime fit, or None."""
    import warnings
    import statsmodels.api as sm
    r = np.asarray(returns, dtype=float)
    if len(r) < MIN_RETURNS:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.tsa.MarkovRegression(r, k_regimes=2, trend="c", switching_variance=True)
        fit = model.fit(disp=False, search_reps=5)
    return {"params": [float(x) for x in fit.params], "names": list(model.param_names)}


def filtered_drift(returns, fitted):
    """Today's drift: the filtered regime probabilities times the regime means."""
    import warnings
    import statsmodels.api as sm
    r = np.asarray(returns, dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.tsa.MarkovRegression(r, k_regimes=2, trend="c", switching_variance=True)
        probs = model.filter(np.asarray(fitted["params"])).filtered_marginal_probabilities
    probs = probs.values if hasattr(probs, "values") else np.asarray(probs)
    means = np.array([p for p, name in zip(fitted["params"], fitted["names"]) if name.startswith("const")])
    return float(probs[-1] @ means), [float(x) for x in probs[-1]]


def growth_share(mu, variance):
    """The growth-optimal share in gold, f* = clip(mu / sigma^2, 0, 1)."""
    if variance is None or variance <= 0 or mu is None:
        return None
    return float(np.clip(mu / variance, 0.0, 1.0))


def cost_band(f_star, round_trip_pct):
    """Half-width of the no-trade band around f* for a round-trip cost in percent."""
    c = round_trip_pct / 100
    return float((1.5 * c * f_star ** 2 * (1 - f_star) ** 2) ** (1 / 3))


def growth_path(close, fitted):
    """(f*, mu) for every day of `close` (f* NaN and mu 0 on the first), filtered forward with one
    fit: the room's brake member reads f* day by day and its 20-day range centres on mu
    (analysis/room.py). Each day's value uses returns up to that day only; the fit is the quarter's."""
    import warnings
    import statsmodels.api as sm
    r = log_returns(close)
    out = np.full(len(r) + 1, np.nan)
    drift = np.zeros(len(r) + 1)
    if len(r) < MIN_RETURNS or not fitted:
        return out, drift
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.tsa.MarkovRegression(r, k_regimes=2, trend="c", switching_variance=True)
        probs = model.filter(np.asarray(fitted["params"])).filtered_marginal_probabilities
    probs = probs.values if hasattr(probs, "values") else np.asarray(probs)
    means = np.array([p for p, name in zip(fitted["params"], fitted["names"]) if name.startswith("const")])
    mu = probs @ means
    v = np.var(r[:60])
    for k, x in enumerate(r):
        v = EWMA_LAMBDA * v + (1 - EWMA_LAMBDA) * x * x
        out[k + 1] = np.clip(mu[k] / v, 0.0, 1.0) if v > 0 else np.nan
        drift[k + 1] = mu[k]
    return out, drift


def assess(close, fitted=None):
    """The engine's view on completed daily closes: {"mu", "variance", "f_star", "probs",
    "fitted"}; `fitted` is refitted when absent. None without enough history."""
    r = log_returns(close)
    if len(r) < MIN_RETURNS:
        return None
    fitted = fitted or fit_regimes(r)
    if not fitted:
        return None
    mu, probs = filtered_drift(r, fitted)
    variance = ewma_variance(r)
    return {"mu": mu, "variance": variance, "f_star": growth_share(mu, variance), "probs": probs, "fitted": fitted}
