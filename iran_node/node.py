"""The Iran-side node (SP_D_HANDOFF.md section 30).

Runs on the owner's phone in Termux, from an Iranian connection, and reads what GitHub's
runner cannot reach: Daric (403 to the runner since 2026-10-03); and Taline, HoorGold and
MioGold, whose pages the runner may be served as an old copy, to compare with production's
(section 31); and TSETMC's daily money flow of the gold funds (section 33), which TSETMC gives
only to Iranian addresses. Each reading goes to Neon's HTTPS endpoint as one row of
iran_node_readings; production reads Daric's from there.

Needs Python, requests and beautifulsoup4 (the repository's collectors parse the three
pages). Settings live in ~/.iran_node.env, never in the repo:

    NEON_URL=postgresql://iran_node:<password>@<host>/neondb?sslmode=require
    NODE=s10

The iran_node role may only INSERT into iran_node_readings. When Neon cannot be reached the
reading waits in ~/iran_node_spool.jsonl and goes with the next run, so a cut of the
international link loses nothing.

    python node.py           read and send (cron runs this every 15 minutes)
    python node.py --test    read and print; send nothing
    python node.py --setup   ask for the node's password, write ~/.iran_node.env, send once
"""

import importlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

# Production's pooled endpoint. Not a secret -- the password is, and the iran_node role may only
# INSERT into iran_node_readings -- but here so the phone types a short password, not a URL.
NEON_HOST = "ep-sweet-bread-agb1w6wg-pooler.c-2.eu-central-1.aws.neon.tech"

HOME = os.path.expanduser("~")
ENV_FILE = os.path.join(HOME, ".iran_node.env")
STATE_FILE = os.path.join(HOME, ".iran_node_state.json")
SPOOL = os.path.join(HOME, "iran_node_spool.jsonl")
LOG = os.path.join(HOME, "iran_node.log")
SPOOL_LIMIT = 3000          # about a month at four readings an hour

DARIC = "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice"
HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G973F) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36",
           "Accept": "application/json"}

# Platforms whose page the runner may be served as an old copy (SP_D_HANDOFF.md section 32):
# read from Iran as well, through the repository's own collectors, so production's stored value
# can be set against what Iran saw at the same minute. Needs beautifulsoup4 on the phone.
COMPARED = (("taline", "TALINE_18K", "collector.taline", "get_taline_price"),
            ("hoorgold", "HOORGOLD_18K", "collector.hoorgold", "get_hoorgold_price"),
            ("miogold", "MIOGOLD_18K", "collector.miogold", "get_miogold_price"))
REPO_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")

# TSETMC's money flow for the room's money-flow member (SP_D_HANDOFF.md sections 24, 27, 33): each
# gold fund's day, individuals and institutions, buy and sell, value and count. TSETMC refuses
# addresses outside Iran. The 19 funds of the research record (research/data/tsetmc_gold_funds.json,
# 2026-10-04), so production's history and the node's days are one series. A day is published once
# it has closed; the last TSETMC_DAYS are asked for in the run of each hour's first quarter until
# every fund has it, and what was fetched is remembered in ~/.iran_node_state.json.
TSETMC_DAY = "https://cdn.tsetmc.com/api/ClientType/GetClientTypeHistory/{code}/{day}"
TSETMC_DAYS = 7
GOLD_FUNDS = (("34144395039913458", "عيار"), ("6362118829011821", "ليان"), ("46700660505281786", "طلا"),
              ("17248898258246807", "درنا"), ("68376789401977331", "گلديس"), ("30582275818828857", "ناب"),
              ("25559236668122210", "كهربا"), ("33254899395816171", "زر"), ("12390706505809150", "گوهر"),
              ("32469128621155736", "مثقال"), ("28374437855144739", "آلتون"), ("38544104313215500", "جواهر"),
              ("4626686276232042", "نفيس"), ("28255729477187163", "زروان"), ("9089296888187061", "تابش"),
              ("6237807001018762", "قيراط"), ("61805666737517582", "درخشان"), ("51200575796028449", "سافرون"),
              ("33144542989832366", "زرفام"))

COLUMNS = ("node", "source", "instrument", "observed_at", "bid", "ask", "value", "status", "detail",
           "payload")
INSERT = (f"INSERT INTO iran_node_readings ({', '.join(COLUMNS)}) VALUES "
          f"({', '.join(f'${i}' for i in range(1, len(COLUMNS) + 1))})")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def log(message):
    line = f"{utc_now()}Z {message}"
    print(line)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def settings():
    values = {}
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def read_daric():
    """Daric's order book, rial: ask is what a buyer pays, bid what a seller is paid."""
    row = {"source": "daric", "instrument": "DARIC_18K", "bid": None, "ask": None, "value": None,
           "status": "ERROR", "detail": None, "payload": None}
    try:
        r = requests.get(DARIC, headers=HEADERS, timeout=(5, 15))
        r.raise_for_status()
        data = r.json()["Data"]
        row.update(ask=float(data["BestSellPrice"]) * 10, bid=float(data["BestBuyPrice"]) * 10,
                   status="OK", payload=data)
    except Exception as e:  # noqa: BLE001 -- an error is a reading too
        row["detail"] = f"{type(e).__name__}: {e}"[:300]
    return row


def read_compared():
    """Taline, HoorGold and MioGold as Iran sees them: the price in `value`, both sides where
    the platform publishes them. One failure does not stop the others."""
    if REPO_SRC not in sys.path:
        sys.path.insert(0, REPO_SRC)
    rows = []
    for source, instrument, module, function in COMPARED:
        row = {"source": source, "instrument": instrument, "bid": None, "ask": None, "value": None,
               "status": "ERROR", "detail": None, "payload": None}
        try:
            result = getattr(importlib.import_module(module), function)()
            row.update(value=float(result["price"]), bid=result.get("sell"), ask=result.get("buy"),
                       status="OK")
        except Exception as e:  # noqa: BLE001
            row["detail"] = f"{type(e).__name__}: {e}"[:300]
        rows.append(row)
    return rows


def read_tsetmc(remember=True, any_minute=False):
    """Each gold fund's closed days not yet fetched, among the last TSETMC_DAYS: one row per fund and
    day, the trading day in `detail`, TSETMC's own record in `payload`. Asked once an hour."""
    tehran = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    if tehran.minute >= 15 and not any_minute:
        return []
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    days = [(tehran.date() - timedelta(days=k)).strftime("%Y%m%d") for k in range(TSETMC_DAYS)]
    done = {key for key in state.get("tsetmc_done", []) if key[:8] in days}
    rows = []
    for day in days:
        for code, symbol in GOLD_FUNDS:
            if f"{day}:{code}" in done:
                continue
            try:
                r = requests.get(TSETMC_DAY.format(code=code, day=day), headers=HEADERS, timeout=(5, 15))
                record = r.json().get("clientType") if r.status_code == 200 else None
            except Exception:  # noqa: BLE001 -- not published yet, or TSETMC down: next hour
                record = None
            if record:
                rows.append({"source": "tsetmc", "instrument": f"CLIENTTYPE_{code}", "bid": None, "ask": None,
                             "value": None, "status": "OK", "detail": day, "payload": record})
                done.add(f"{day}:{code}")
    if remember:
        state["tsetmc_done"] = sorted(done)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    return rows


def describe(row):
    if row["status"] != "OK":
        return f"{row['source']} ERROR {row['detail']}"
    if row["value"] is not None:
        return f"{row['source']} {row['value']:,.0f}"
    return f"{row['source']} bid {row['bid']:,.0f} ask {row['ask']:,.0f}"


def send(row, neon_url):
    """One INSERT through Neon's HTTPS endpoint (no Postgres port needed)."""
    host = urlparse(neon_url).hostname
    params = [json.dumps(row[c]) if c == "payload" and row[c] is not None else row[c] for c in COLUMNS]
    r = requests.post(f"https://{host}/sql", timeout=(10, 30),
                      headers={"Neon-Connection-String": neon_url, "Content-Type": "application/json"},
                      data=json.dumps({"query": INSERT, "params": params}))
    if r.status_code != 200:
        raise RuntimeError(f"Neon {r.status_code}: {r.text[:200]}")


def load_spool():
    if not os.path.exists(SPOOL):
        return []
    with open(SPOOL, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_spool(rows):
    rows = rows[-SPOOL_LIMIT:]
    with open(SPOOL, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def setup():
    """Write ~/.iran_node.env from a typed password, so nothing long is typed on the phone."""
    password = input("node password: ").strip()
    node = input("node name [s10]: ").strip() or "s10"
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(f"NEON_URL=postgresql://iran_node:{password}@{NEON_HOST}/neondb\nNODE={node}\n")
    os.chmod(ENV_FILE, 0o600)
    log(f"settings written to {ENV_FILE}; sending now")


def main(argv):
    if "--setup" in argv:
        setup()
    cfg = settings() if os.path.exists(ENV_FILE) else {}
    node, now = cfg.get("NODE", "s10"), utc_now()
    testing = "--test" in argv
    flows = read_tsetmc(remember=not testing, any_minute=testing)
    readings = [dict(row, node=node, observed_at=now) for row in [read_daric()] + read_compared() + flows]
    summary = "; ".join(describe(row) for row in readings if row["source"] != "tsetmc")
    if flows:
        summary += f"; tsetmc {len(flows)} fund-days ({', '.join(sorted({r['detail'] for r in flows}))})"
    if "--test" in argv:
        log(f"TEST {summary} (nothing sent)")
        return 0
    if "NEON_URL" not in cfg:
        log(f"no NEON_URL in {ENV_FILE}; {summary} kept in the spool")
        save_spool(load_spool() + readings)
        return 1
    queue, unsent, failure = load_spool() + readings, [], None
    for row in queue:
        if failure is None:
            try:
                send(row, cfg["NEON_URL"])
                continue
            except Exception as e:  # noqa: BLE001
                failure = f"{type(e).__name__}: {e}"[:200]
        unsent.append(row)
    save_spool(unsent)
    sent = len(queue) - len(unsent)
    log(f"{summary}; sent {sent}" + (f", waiting {len(unsent)} ({failure})" if unsent else ""))
    return 0 if not unsent else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
