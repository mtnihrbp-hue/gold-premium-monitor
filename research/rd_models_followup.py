"""R3 follow-ups: a stricter new-high target, and a volatility-scaled range for 'how much'."""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import rd_models as m          # reuses the causal anchors and the walk-forward split

gc, n, gd, years, X, complete = m.gc, m.n, m.gd, m.years, m.X, m.complete
hi250 = np.array([gc[max(0, i - 249):i + 1].max() for i in range(n)])
print("\n#### FOLLOW-UP A: a new high that clears the old one by a margin")
for margin in (0.02, 0.05):
    y = np.full(n, np.nan)
    for i in range(n - 20):
        y[i] = float(gc[i + 1:i + 21].max() > hi250[i] * (1 + margin))
    m.binary_report(f"New 52-week high by {margin:.0%} or more within 20 days", y)

print("\n#### FOLLOW-UP B: volatility-scaled range for the 20 and 60-day move")
lr = np.full(n, np.nan); lr[1:] = np.log(gc[1:] / gc[:-1])
sigma = np.array([np.nanstd(lr[max(1, i - 59):i + 1]) if i >= 60 else np.nan for i in range(n)])
for hzn in (20, 60):
    y = m.targets[f"move{hzn}"]
    z = y / (sigma * np.sqrt(hzn) * 100)
    print(f"\n== {hzn}-day move: plain historical quantiles vs volatility-scaled quantiles")
    print("  year  days | 10-90% covered: plain  scaled | pinball skill of scaled vs plain 10% 50% 90%")
    tot = {q: [[], [], []] for q in m.QUANTILES}
    cov_p, cov_s = [], []
    for year in range(m.FIRST_YEAR, gd[-1].year + 1):
        train = m.known_by(year, hzn) & ~np.isnan(y) & ~np.isnan(z)
        test = (years == year) & complete & ~np.isnan(y) & ~np.isnan(sigma)
        if test.sum() < 20:
            continue
        plain = {q: np.full(test.sum(), np.quantile(y[train], q)) for q in m.QUANTILES}
        scaled = {q: np.quantile(z[train], q) * sigma[test] * np.sqrt(hzn) * 100 for q in m.QUANTILES}
        sk = [(1 - m.pinball(q, scaled[q], y[test]) / m.pinball(q, plain[q], y[test])) * 100 for q in m.QUANTILES]
        cp = np.mean((y[test] >= plain[0.1]) & (y[test] <= plain[0.9])) * 100
        cs = np.mean((y[test] >= scaled[0.1]) & (y[test] <= scaled[0.9])) * 100
        cov_p.append((cp, test.sum())); cov_s.append((cs, test.sum()))
        for q in m.QUANTILES:
            tot[q][0].append(scaled[q]); tot[q][1].append(plain[q]); tot[q][2].append(y[test])
        print(f"  {year}  {test.sum():4} |          {cp:5.0f}%  {cs:5.0f}%   |   {sk[0]:+5.0f}% {sk[1]:+5.0f}% {sk[2]:+5.0f}%")
    w = sum(k for _, k in cov_p)
    print(f"  overall coverage: plain {sum(c * k for c, k in cov_p) / w:.0f}%, scaled {sum(c * k for c, k in cov_s) / w:.0f}% (target 80%)")
    for q in m.QUANTILES:
        p, b, yy = (np.concatenate(v) for v in tot[q])
        print(f"  overall {q:.0%} pinball skill of scaled vs plain: {(1 - m.pinball(q, p, yy) / m.pinball(q, b, yy)) * 100:+.1f}%")
    i = n - 1
    q_now = {q: np.quantile(z[~np.isnan(z) & (np.arange(n) < n - hzn)], q) * sigma[i] * np.sqrt(hzn) * 100 for q in m.QUANTILES}
    print(f"  today's scaled range ({gd[i]}, daily vol {sigma[i] * 100:.2f}%): 10% {q_now[0.1]:+.1f}%  50% {q_now[0.5]:+.1f}%  90% {q_now[0.9]:+.1f}%")
