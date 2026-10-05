"""The LLM chair's quarters against holding's, and the weekly committee on the same days (SP-D, 2026-10-05)."""
import json
import sys

import numpy as np

import rd_committee_2y as R
from rd_committee_cadence import every


def chair(path):
    D = json.load(open(path, encoding="utf-8"))
    by_i = {int(x["i"]): x["swing"] for x in D["decisions"] if x.get("swing") in ("GOLD", "FIXED_INCOME")}

    def factory(idx):
        s = {"out": False}

        def f(i):
            if i in by_i:
                s["out"] = by_i[i] == "FIXED_INCOME"
            return s["out"]
        return f
    return D["model"], factory


extra = []
for p in sys.argv[1:]:
    model, fac = chair(p)
    extra.append((f"LLM chair, {model.split('/')[-1]}", fac))
extra.append(("committee, acting weekly on the same days", every(5, 0)))
E = R.evaluate(R.START, R.END, extra=extra)
res, idx = E["res"], E["idx"]
pos = {i: k for k, i in enumerate(idx)}
qs = E["qstarts"] + [idx[-1] + 1]
hv = res["hold (the bar)"]["values"]


def quarters(v):
    out = []
    for a, b in zip(qs[:-1], qs[1:]):
        ka, kb = pos[a], pos[min(b, idx[-1] + 1) - 1]
        base = v[ka - 1] if ka else R.CASH0
        out.append(v[kb] / base - 1)
    return out


hq = quarters(hv)
print("   " + " " * 44 + "".join(f"{R.QL[q]:>9}" for q in E["qstarts"]) + "    2 years")
print("   " + "hold (the quarter's return)".ljust(44) + "".join(f"{x * 100:+8.1f}%" for x in hq)
      + f"   {res['hold (the bar)']['end'] / 1e7:6.1f}M")
for name in [n for n, _ in extra] + ["committee, proposed weights"]:
    v = res[name]["values"]
    print("   " + name[:43].ljust(44) + "".join(f"{(a - b) * 100:+8.1f} " for a, b in zip(quarters(v), hq))
          + f"   {(res[name]['end'] / res['hold (the bar)']['end'] - 1) * 100:+5.1f}%")
