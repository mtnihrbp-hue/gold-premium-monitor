"""The engine's state today, for the forward test (SP_D_HANDOFF.md sections 78.6 and 79): the candidate frozen
from E-8 (77.7-77.8), judged only on days it has not seen.

One run:
1. refreshes the inputs: tgju's histories (direct), CBOE's GVZ and VIX and the IMF's CPI (through the system
   proxy), and rebuilds the research table;
2. fits E-1b's calm model (X, with its fallbacks) and E-5's R3 and R10 on every day whose outcome is complete,
   and scores today;
3. applies the frozen rule:
   - **in:** half into fixed income when R3 >= 0.30;
   - **back:** 3 x the forecast daily volatility x the square root of the days in above the entry close at any
     time, or, after 5 days, R3 below 0.30 with 18K's close above the entry close;
4. appends one line to research/data/shadow_ledger.jsonl: the date, the inputs' last dates, the forecasts, the
   rule's state. The line is written before its outcome exists.

It never sends anything and never touches production.

    python research/engine_today.py [--no-refresh]
"""

import io
import json
import math
import os
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LEDGER = os.path.join(HERE, "data", "shadow_ledger.jsonl")
THRESHOLD, MIN_STAY, HARD_K = 0.30, 5, 3.0
FROZEN = "E-8 candidate, frozen 2026-10-30 (SP_D_HANDOFF.md 77.7-77.8, 79)"


def refresh():
    """Fresh inputs: tgju direct; CBOE and the IMF through the system proxy (Psiphon), whatever its port."""
    subprocess.run([sys.executable, os.path.join(HERE, "fetch_tgju_more.py")], check=True, capture_output=True)
    s = requests.Session()                       # trust_env: the system proxy reaches what Iran cannot
    for name, url in (("gvz.csv", "https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv"),
                      ("vix.csv", "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv")):
        r = s.get(url, timeout=90, headers={"User-Agent": "Mozilla/5.0"})
        if r.ok and r.text.startswith("DATE"):
            open(os.path.join(HERE, "data", name), "w", encoding="utf-8").write(r.text)
    macro_path = os.path.join(HERE, "data", "macro.json")
    macro = json.load(open(macro_path, encoding="utf-8"))
    for key, country in (("cpi_iran", "IRN"), ("cpi_us", "USA")):
        try:
            d = s.get(f"https://api.imf.org/external/sdmx/2.1/data/IMF.STA,CPI/{country}.CPI._T.IX.M", timeout=90,
                      headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}).json()
            obs = d["structure"]["dimensions"]["observation"][0]["values"]
            ser = next(iter(d["dataSets"][0]["series"].values()))["observations"]
            macro[key] = sorted((obs[int(k)]["id"], float(v[0])) for k, v in ser.items() if v and v[0] is not None)
        except Exception as e:  # noqa: BLE001 -- the last copy stays
            print(f"CPI {country} not refreshed: {e}")
    json.dump(macro, open(macro_path, "w"), indent=0)
    import build_flows
    import build_panel
    with redirect_stdout(io.StringIO()):
        try:
            build_flows.main()
        except Exception as e:  # noqa: BLE001 -- the flows are not the candidate's inputs
            print(f"flows not rebuilt: {e}")
        build_panel.main()


def calm_today(rows):
    import rd_engine_calm as e1
    X, y = e1.build(rows)
    n = len(rows)
    train = [j for j in range(n - 21) if y[j] is not None]
    use = list(e1.X_NAMES)
    today = X[-1]
    for k in list(use):
        if today[k] is None:
            use.remove(k)
    tr = [(X[j], y[j]) for j in train if all(X[j][k] is not None for k in use)]
    pred = e1.fit_predict(tr, [today], use, e1.RIDGE)[0]
    return float(pred), use


def risk_today(rows, calm_series):
    import rd_fall_risk as e5
    import rd_windows_read as g4
    macro = json.load(open(os.path.join(HERE, "data", "macro.json"), encoding="utf-8"))
    F = g4.drivers(rows, macro, calm_series)
    y = e5.target(rows)
    n = len(rows)
    train = [j for j in range(n - 41) if y[j] is not None and rows[j]["date"] >= "2015-03-15"]
    out = {}
    for name, cols in (("R3", e5.R3), ("R10", e5.R10)):
        use = [k for k in cols if F[-1][k] is not None]
        got = e5.fit(train, [n - 1], F, y, use, 0.3)
        out[name] = got.get(n - 1)
        out[name + "_inputs"] = {k: F[-1][k] for k in use}
    return out


def main():
    if "--no-refresh" not in sys.argv:
        refresh()
    with open(os.path.join(HERE, "data", "panel.json"), encoding="utf-8") as f:
        rows = json.load(f)["rows"]
    calm_path = os.path.join(HERE, "data", "calm_forecasts_b.json")
    calm_series = json.load(open(calm_path, encoding="utf-8")) if os.path.exists(calm_path) else {}
    calm, used = calm_today(rows)
    calm_series[rows[-1]["date"]] = dict(calm_series.get(rows[-1]["date"], {}), X=calm)
    risk = risk_today(rows, calm_series)
    last = rows[-1]
    lines = [json.loads(l) for l in open(LEDGER, encoding="utf-8")] if os.path.exists(LEDGER) else []
    prev = lines[-1] if lines else {"state": "gold"}
    state, entry = prev.get("state", "gold"), prev.get("entry")
    action = "hold"
    if lines and lines[-1]["date"] == last["date"]:
        print(f"already recorded for {last['date']}")
        return
    if state == "gold" and risk["R3"] is not None and risk["R3"] >= THRESHOLD:
        state, action = "half", "in: half into fixed income at the next close"
        entry = {"date": last["date"], "g18": last["g18"], "sigma": math.exp(calm)}
    elif state == "half" and entry:
        days = sum(1 for r in rows if r["date"] > entry["date"])
        rise = math.log(last["g18"] / entry["g18"])
        if rise > HARD_K * entry["sigma"] * math.sqrt(max(days, 1)):
            state, action, entry = "gold", "back: the hard stop", None
        elif days >= MIN_STAY and risk["R3"] is not None and risk["R3"] < THRESHOLD and last["g18"] > entry["g18"]:
            state, action, entry = "gold", "back: the risk has passed and the price recovered", None
    line = {"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rule": FROZEN, "date": last["date"],
            "g18": last["g18"], "usd": last["usd"], "inputs_last": {k: max((r["date"] for r in rows if r.get(k) is not None), default=None)
                                                                     for k in ("g18", "usd", "tether", "coin", "gvz_prev", "fi")},
            "calm_daily_vol": math.exp(calm), "R3": risk["R3"], "R10": risk["R10"], "state": state, "action": action,
            "entry": entry}
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print(json.dumps({k: line[k] for k in ("date", "calm_daily_vol", "R3", "R10", "state", "action")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
