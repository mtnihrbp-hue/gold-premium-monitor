"""Today's values of the validated anchors (fitted on every outcome known today)."""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
import rd_models as m

gc, n, X, complete, gd = m.gc, m.n, m.X, m.complete, m.gd
hi250 = np.array([gc[max(0, i - 249):i + 1].max() for i in range(n)])
i = n - 1
for margin, label in ((0.0, "new 52-week high"), (0.02, "new 52-week high by 2%+")):
    y = np.full(n, np.nan)
    for k in range(n - 20):
        y[k] = float(gc[k + 1:k + 21].max() > hi250[k] * (1 + margin))
    train = complete & ~np.isnan(y)
    gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, l2_regularization=1.0,
                                        random_state=7).fit(X[train], y[train])
    print(f"P({label} within 20 trading days) today: {gb.predict_proba(X[i:i + 1])[0, 1] * 100:.0f}%   "
          f"(all days since 2014: {y[train].mean() * 100:.0f}%)")
print(f"close {gd[i]} {gc[i] / 1e7:.2f} M; 52-week high {hi250[i] / 1e7:.2f} M; +2% above it = {hi250[i] * 1.02 / 1e7:.2f} M")
