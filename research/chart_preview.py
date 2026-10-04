"""Render the analyst's chart from the stored history, for the owner's review (SP-D).
Writes research/data/chart_preview.png (git-ignored)."""
import json
import os
import sys
from collections import defaultdict
from datetime import date

import numpy as np
import talib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from caluclator.technical import split_levels, swing_levels, volume_profile
from alerts.chart import render

rows = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))["geram18"]
F = json.load(open(os.path.join(HERE, "data", "tsetmc_gold_funds.json"), encoding="utf-8"))
d = [date.fromisoformat(r["date"]) for r in rows]
o, h, l, c = (np.array([float(r[k]) for r in rows]) for k in ("open", "high", "low", "close"))
value = defaultdict(float)
for f in F.values():
    if f["symbol"] != "سافرون":
        for p in f["prices"]:
            value[p["date"]] += p["value"]
v = np.array([value.get(x.strftime("%Y%m%d"), 0.0) for x in d])
i = len(c) - 1
usable = [not (o[j] == h[j] == l[j] == c[j]) and l[j] <= min(o[j], c[j]) and h[j] >= max(o[j], c[j]) for j in range(len(c))]
live = 265_881_280.0                                 # Daric's bid, 2026-10-04 13:00
sup, res = split_levels(swing_levels(h, l, upto=i, usable=usable), live)
va = volume_profile(h, l, c, v, upto=i)
png = render(d, o, h, l, c, ema20=talib.EMA(c, 20), ema50=talib.EMA(c, 50),
             supports=[x["price"] for x in sup[:3]], resistances=[x["price"] for x in res[:2]],
             value_area=va, trades=[(d[-1], "BUY", 266_904_610.0)], live=live,
             title="18K daily · support/resistance (swings) · value area (gold-fund volume) · PAPER trades")
out = os.path.join(HERE, "data", "chart_preview.png")
open(out, "wb").write(png)
print("wrote", out, len(png), "bytes; supports", [round(x["price"] / 1e7, 2) for x in sup[:3]],
      "resistances", [round(x["price"] / 1e7, 2) for x in res[:2]], "value area", {k: round(x / 1e7, 2) for k, x in va.items()})
