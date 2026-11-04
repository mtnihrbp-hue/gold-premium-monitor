"""A first look at the gold funds' in-session record (SP_D_HANDOFF.md sections 48.2 and 95; exploratory, not a
registered test): the phone's `tsetmc_live` reads, every 15 minutes from 12:00 to 18:15 Tehran, for the 19 funds
together. For each session:
- the value traded by 14:00 and by the close, against the median of the other sessions at the same time;
- individuals' net money (buy minus sell volume, at the last price) by the close;
- the largest 15-minute step in value traded inside 12:00-18:00, as a share of a usual whole day, beside that
  slot's usual share (the read after 18:00 is left out: almost nothing trades then, so any step looks huge).

The registered study waits for about 60 sessions (48.2). Read-only against production; prints only.

    python research/rd_fund_live_look.py
"""

import os
import statistics as st
from collections import defaultdict
from datetime import timedelta

import psycopg2


def load():
    url = os.environ.get("DATABASE_URL") or open(os.path.expanduser("~/.gpm_neon_url")).read().strip()
    c = psycopg2.connect(url)
    c.set_session(readonly=True)
    q = c.cursor()
    q.execute("""select observed_at, instrument, payload from iran_node_readings
                 where source = 'tsetmc_live' and status = 'OK' order by observed_at""")
    return q.fetchall()


def sessions(rows):
    """{day: {slot "HH:MM": (value so far, individuals' net so far)}}, the 19 funds summed; a slot is a read."""
    by = defaultdict(lambda: defaultdict(dict))
    for at, fund, p in rows:
        t = at + timedelta(hours=3, minutes=30)
        slot = f"{t.hour:02d}:{t.minute // 15 * 15:02d}"
        by[t.date()][slot][fund] = p
    out = {}
    for day, slots in by.items():
        out[day] = {}
        for slot, funds in sorted(slots.items()):
            value = sum(float(p.get("qTotCap") or 0) for p in funds.values())
            net = sum((float(p.get("buy_I_Volume") or 0) - float(p.get("sell_I_Volume") or 0)) * float(p.get("pDrCotVal") or 0)
                      for p in funds.values())
            out[day][slot] = (value, net, len(funds))
    return out


def main():
    data = sessions(load())
    full = {d: s for d, s in data.items() if len(s) >= 24}            # a whole session: 26 reads, a little slack
    print(f"sessions: {len(data)}, whole: {len(full)} ({', '.join(str(d) for d in sorted(set(data) - set(full)))} partial)")
    days = sorted(full)
    bil = 1e10                                                          # rial to billion toman
    for d in days:
        s = full[d]
        others = [full[o] for o in days if o != d]
        def usual(slot, k=0):
            v = [o[slot][k] for o in others if slot in o]
            return st.median(v) if v else None
        close = max(s)
        at14 = "14:00" if "14:00" in s else None
        v14, u14 = (s[at14][0], usual(at14)) if at14 else (None, None)
        vc, uc = s[close][0], usual(close)
        slots = [x for x in sorted(s) if "12:00" <= x <= "18:00"]
        day_usual = st.median(o[max(o)][0] for o in others)            # a usual whole session's value
        steps = []
        for a, b in zip(slots, slots[1:]):
            share = (s[b][0] - s[a][0]) / day_usual
            usual_share = st.median((o[b][0] - o[a][0]) / day_usual for o in others if a in o and b in o)
            steps.append((share, b, usual_share))
        top = max(steps)
        print(f"{d} {d.strftime('%a')}: by 14:00 {v14 / bil:6.0f} bn toman ({v14 / u14:4.1f}x usual) | close {vc / bil:6.0f}"
              f" ({vc / uc:4.1f}x) | individuals net {s[close][1] / bil:+6.0f} | top 15 min {top[0]:4.0%} of a usual day"
              f" at {top[1]} (usual {top[2]:3.0%})" if at14 else f"{d}: no 14:00 read")


if __name__ == "__main__":
    main()
