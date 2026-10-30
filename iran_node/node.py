"""The Iran-side node (SP_D_HANDOFF.md section 30).

Runs on the owner's phone in Termux, from an Iranian connection, and reads what GitHub's
runner cannot reach: Daric (403 to the runner since 2026-10-03); and TSETMC's daily money flow
of the gold funds (section 33), which TSETMC gives only to Iranian addresses, and its live flow
inside the session (section 48). Each reading goes to Neon's HTTPS endpoint as one row of
iran_node_readings; production reads Daric's and TSETMC's days from there. Taline, HoorGold and
MioGold, read here from 10-06 to compare Iran's view with the runner's (section 31), are no longer
read: the study ended and production never read them (SP_D_HANDOFF.md 73.9).

Needs Python and requests. Settings live in ~/.iran_node.env, never in the repo:

    NEON_URL=postgresql://iran_node:<password>@<host>/neondb?sslmode=require
    NODE=s10

The iran_node role may only INSERT into iran_node_readings. When Neon cannot be reached the
reading waits in ~/iran_node_spool.jsonl and goes with the next run, so a cut of the
international link loses nothing.

    python node.py           read and send (cron runs this every 15 minutes)
    python node.py --test    read and print; send nothing
    python node.py --setup   ask for the node's password, write ~/.iran_node.env, send once
"""

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
# Readings kept while Neon cannot be reached. Since TSETMC joined (about 400 rows a day) 3,000 was
# seven days; Neon's free plan suspended the database on 2026-10-13 until the month's end
# (SP_D_HANDOFF.md section 34), so the spool must hold a month: about 12,000 rows, kept with room.
SPOOL_LIMIT = 30000
# A row Neon refuses for its own content (SQLSTATE class 22, a data exception; 23, a constraint) would stop the
# queue behind it for good. It is set aside here instead, and the rest go on (the external audit's A9;
# SP_D_HANDOFF.md section 52). Anything else -- the network, the quota of 10-13 -- still stops the queue.
REJECTED = os.path.join(HOME, "iran_node_rejected.jsonl")
LOCK = os.path.join(HOME, ".iran_node.lock")
_LOCK_FILE = None                # held open for the run: the lock lives as long as the file
ROW_ERRORS = ("22", "23")
NO_SESSION_AFTER_DAYS = 3        # a closed day still without a record 3 days on had no session (a holiday)

DARIC = "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice"
HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G973F) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36",
           "Accept": "application/json"}


# TSETMC's money flow for the room's money-flow member (SP_D_HANDOFF.md sections 24, 27, 33): each
# gold fund's day, individuals and institutions, buy and sell, value and count. TSETMC refuses
# addresses outside Iran. The 19 gold funds of the research record (research/data/tsetmc_gold_funds.json,
# 2026-10-04; گنج added 2026-10-17, SP_D_HANDOFF.md section 48; سافرون, a saffron fund, removed 2026-10-18,
# section 49), so production's history and the node's days are one series. A day is published once
# it has closed; the last TSETMC_DAYS are asked for in the run of each hour's first quarter until
# every fund has it, and what was fetched is remembered in ~/.iran_node_state.json.
TSETMC_DAY = "https://cdn.tsetmc.com/api/ClientType/GetClientTypeHistory/{code}/{day}"
TSETMC_DAYS = 7
GOLD_FUNDS = (("34144395039913458", "عيار"), ("6362118829011821", "ليان"), ("46700660505281786", "طلا"),
              ("17248898258246807", "درنا"), ("68376789401977331", "گلديس"), ("30582275818828857", "ناب"),
              ("25559236668122210", "كهربا"), ("33254899395816171", "زر"), ("12390706505809150", "گوهر"),
              ("32469128621155736", "مثقال"), ("28374437855144739", "آلتون"), ("38544104313215500", "جواهر"),
              ("4626686276232042", "نفيس"), ("28255729477187163", "زروان"), ("9089296888187061", "تابش"),
              ("6237807001018762", "قيراط"), ("61805666737517582", "درخشان"),
              ("33144542989832366", "زرفام"), ("58514988269776425", "گنج"))

# TSETMC's live money flow of the same funds inside their session (owner, 2026-10-17: "are we collecting the
# tsetmc data hourly on a business day or only after the market closes. if it is hourly the data is much more
# valuable for identifying hot money"; SP_D_HANDOFF.md section 48). TSETMC keeps no intraday history of who
# bought, so it exists only if it is recorded as it happens: every run from 12:00 to 18:15 Tehran, Saturday to
# Wednesday, each fund's individuals' and institutions' buying and selling so far, and its price, volume and
# value so far, as source "tsetmc_live". Kept for research; production reads only "tsetmc".
TSETMC_LIVE_FLOW = "https://cdn.tsetmc.com/api/ClientType/GetClientType/{code}/1/0"
TSETMC_LIVE_PRICE = "https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceInfo/{code}"
LIVE_FROM, LIVE_TO = 12 * 60, 18 * 60 + 15             # minutes of the Tehran day
LIVE_FLOW_KEYS = ("buy_I_Volume", "buy_N_Volume", "buy_CountI", "buy_CountN",
                  "sell_I_Volume", "sell_N_Volume", "sell_CountI", "sell_CountN")
LIVE_PRICE_KEYS = ("dEven", "hEven", "pDrCotVal", "qTotTran5J", "qTotCap", "zTotTran", "priceYesterday")

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


class RowRefused(RuntimeError):
    """Neon refused this row for its content; the next rows can still go."""


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
    dates = [tehran.date() - timedelta(days=k) for k in range(TSETMC_DAYS)]
    days = [d.strftime("%Y%m%d") for d in dates]
    done = {key for key in state.get("tsetmc_done", []) if key[:8] in days}
    rows = []
    for date_, day in zip(dates, days):
        if date_.weekday() in (3, 4):
            continue                     # Thursday and Friday: no session, nothing to ask (A9)
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
            elif (tehran.date() - date_).days >= NO_SESSION_AFTER_DAYS:
                done.add(f"{day}:{code}")    # still nothing 3 days on: a holiday, not asked again
    if remember:
        state["tsetmc_done"] = sorted(done)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    return rows


def read_tsetmc_live(tehran=None, any_minute=False):
    """Each gold fund's money flow so far today, during the funds' session (TSETMC_LIVE_FLOW above): one row
    per fund that has traded, the day and TSETMC's time in `detail`, the cumulative figures in `payload`."""
    tehran = tehran or datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    minute = tehran.hour * 60 + tehran.minute
    if not any_minute and (tehran.weekday() in (3, 4) or not LIVE_FROM <= minute <= LIVE_TO):
        return []                                        # Thursday, Friday, or outside the session
    rows = []
    for code, _symbol in GOLD_FUNDS:
        try:
            flow = requests.get(TSETMC_LIVE_FLOW.format(code=code), headers=HEADERS, timeout=(5, 10)).json()
            price = requests.get(TSETMC_LIVE_PRICE.format(code=code), headers=HEADERS, timeout=(5, 10)).json()
            flow, price = flow.get("clientType") or {}, price.get("closingPriceInfo") or {}
        except Exception:  # noqa: BLE001 -- TSETMC slow or down: the next run
            continue
        if not price.get("qTotTran5J"):
            continue                                     # no trade yet today, or a holiday
        payload = {k: flow.get(k) for k in LIVE_FLOW_KEYS}
        payload.update({k: price.get(k) for k in LIVE_PRICE_KEYS})
        rows.append({"source": "tsetmc_live", "instrument": f"CLIENTTYPE_{code}", "bid": None, "ask": None,
                     "value": None, "status": "OK", "detail": f"{price.get('dEven')}-{price.get('hEven')}",
                     "payload": payload})
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
        try:
            code = str(r.json().get("code") or "")
        except ValueError:
            code = ""
        if code[:2] in ROW_ERRORS:
            raise RowRefused(f"Neon {r.status_code} {code}: {r.text[:200]}")
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


def locked():
    """True when another run holds the lock: cron runs every 15 minutes, and a slow run must not have a second
    one rewrite the same spool beside it (A9). Without fcntl (not on the phone) there is no lock."""
    try:
        import fcntl
    except ImportError:
        return False
    global _LOCK_FILE
    _LOCK_FILE = open(LOCK, "w")
    try:
        fcntl.flock(_LOCK_FILE, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


def main(argv):
    if "--setup" in argv:
        setup()
    if "--test" not in argv and locked():
        log("the previous run is still going; this one stops")
        return 0
    cfg = settings() if os.path.exists(ENV_FILE) else {}
    node, now = cfg.get("NODE", "s10"), utc_now()
    testing = "--test" in argv
    flows = read_tsetmc(remember=not testing, any_minute=testing)
    try:
        live = read_tsetmc_live(any_minute=testing)
    except Exception as e:  # noqa: BLE001 -- the research read must never cost Daric's reading
        live = []
        log(f"tsetmc live failed: {type(e).__name__}")
    readings = [dict(row, node=node, observed_at=now) for row in [read_daric()] + flows + live]
    summary = "; ".join(describe(row) for row in readings if row["source"] not in ("tsetmc", "tsetmc_live"))
    if flows:
        summary += f"; tsetmc {len(flows)} fund-days ({', '.join(sorted({r['detail'] for r in flows}))})"
    if live:
        summary += f"; tsetmc live {len(live)} funds"
    if "--test" in argv:
        log(f"TEST {summary} (nothing sent)")
        return 0
    if "NEON_URL" not in cfg:
        log(f"no NEON_URL in {ENV_FILE}; {summary} kept in the spool")
        save_spool(load_spool() + readings)
        return 1
    queue, unsent, refused, failure = load_spool() + readings, [], [], None
    for row in queue:
        if failure is None:
            try:
                send(row, cfg["NEON_URL"])
                continue
            except RowRefused as e:
                refused.append(dict(row, refused=str(e)[:200]))
                continue
            except Exception as e:  # noqa: BLE001
                failure = f"{type(e).__name__}: {e}"[:200]
        unsent.append(row)
    save_spool(unsent)
    if refused:
        with open(REJECTED, "a", encoding="utf-8") as f:
            for row in refused:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    sent = len(queue) - len(unsent) - len(refused)
    log(f"{summary}; sent {sent}" + (f", set aside {len(refused)} refused rows in {REJECTED}" if refused else "")
        + (f", waiting {len(unsent)} ({failure})" if unsent else ""))
    return 0 if not unsent else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
