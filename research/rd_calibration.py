"""Calibration of the walk-forward new-high forecasts: when the model said X%, how often?"""
import io
from contextlib import redirect_stdout
import numpy as np
with redirect_stdout(io.StringIO()):
    import rd_models as m
gc, n = m.gc, m.n
hi250 = np.array([gc[max(0, i - 249):i + 1].max() for i in range(n)])
for margin, label in ((0.0, "new 52-week high"), (0.02, "new high by 2%+")):
    y = np.full(n, np.nan)
    for k in range(n - 20):
        y[k] = float(gc[k + 1:k + 21].max() > hi250[k] * (1 + margin))
    with redirect_stdout(io.StringIO()):
        agg = m.binary_report(label, y)
    p, yy = np.concatenate(agg["gb"]), np.concatenate(agg["y"])
    print(f"\n{label} -- boosted, walk-forward 2017-2026 ({len(p)} days)")
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, .9), (.9, 1.01)):
        sel = (p >= lo) & (p < hi)
        if sel.sum():
            print(f"  forecast {lo*100:3.0f}-{min(hi,1)*100:3.0f}%: {sel.sum():4} days, happened {yy[sel].mean()*100:4.0f}%")
