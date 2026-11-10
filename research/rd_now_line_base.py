"""The NOW line's 18K on eight platforms against gram platforms only, and each against tgju's close, read-only (SP_D_HANDOFF.md 111.4).

    python research/rd_now_line_base.py
"""
import os
import statistics as st
import sys
from collections import defaultdict
from datetime import timedelta

import psycopg2

sys.stdout.reconfigure(encoding="utf-8")
c = psycopg2.connect(open(os.path.expanduser("~/.gpm_neon_url")).read().strip())
c.set_session(readonly=True)
q = c.cursor()
EIGHT = ("HoorGold", "Parasteh", "Daric", "Ayyareh", "Invi", "Goldika", "Milli", "WallGold")
GRAM = ("Daric", "Ayyareh", "Invi", "Goldika", "Milli", "WallGold")
q.execute("""select s.id, s.timestamp, p.platform_name, p.price_irr from market_snapshots s join platform_prices p on p.snapshot_id = s.id
             where s.collection_mode = 'scheduled' and s.timestamp >= '2026-09-29' and p.platform_name = any(%s) order by s.timestamp""", (list(EIGHT),))
snaps = {}
for sid, t, n, v in q.fetchall():
    snaps.setdefault(sid, {"t": t, "p": {}})["p"][n] = float(v)
q.execute("select trade_date, close from market_daily_candles where source='tgju' and instrument='TGJU_GOLD_18K' and trade_date >= '2026-09-29' order by 1")
tgju = {d: float(v) for d, v in q.fetchall()}
OFF = 1.0019
T = timedelta(hours=3, minutes=30)
days = defaultdict(list)
for s in sorted(snaps.values(), key=lambda x: x["t"]):
    days[(s["t"] + T).date()].append(s)
print("readings", len(snaps), "days", len(days), "tgju closes", len(tgju))
print("platforms present per reading:", {k: sum(1 for s in snaps.values() if len(s["p"]) == k) for k in range(5, 9)})
diff, a_gap, g_gap = [], [], []
for s in snaps.values():
    a = st.median(s["p"].values()) * OFF
    g = st.median([v for k, v in s["p"].items() if k in GRAM]) * OFF
    diff.append((a / g - 1) * 100)
print(f"eight-platform figure minus gram-only: typical {st.median(diff):+.2f}%  p5 {sorted(diff)[len(diff)//20]:+.2f}%  p95 {sorted(diff)[-len(diff)//20]:+.2f}%")
series = []
for d in sorted(days):
    s = days[d][-1]
    a = st.median(s["p"].values()) * OFF
    g = st.median([v for k, v in s["p"].items() if k in GRAM]) * OFF
    w = s["p"].get("WallGold")
    series.append((d, a, g, w, tgju.get(d), len(s["p"])))
for label, k in (("eight platforms", 1), ("gram only", 2)):
    e = [abs(r[k] / r[4] - 1) * 100 for r in series if r[4]]
    print(f"{label}: the day's last figure against that day's tgju close: typical {st.median(e):.2f}%, largest {max(e):.2f}%  (n {len(e)})")
pairs = [(series[i], series[i + 3]) for i in range(len(series) - 3)]
disagree = sum((b[1] > a[1]) != (b[2] > a[2]) for a, b in pairs)
print(f"3 nights later, 'higher' on the eight-platform figure disagrees with the gram-only figure: {disagree} of {len(pairs)}")
t_pairs = [(a, b) for a, b in pairs if a[4] and b[4]]
print(f"against tgju's own close: eight-platform disagrees {sum((b[1] > a[1]) != (b[4] > a[4]) for a, b in t_pairs)} of {len(t_pairs)}; gram-only disagrees {sum((b[2] > a[2]) != (b[4] > a[4]) for a, b in t_pairs)} of {len(t_pairs)}")
small = [abs(b[1] / a[1] - 1) * 100 for a, b in pairs]
print(f"typical 3-night move of the figure: {st.median(small):.2f}%")
