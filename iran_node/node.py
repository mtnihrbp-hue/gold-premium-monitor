"""The Iran-side node (SP_D_HANDOFF.md section 30).

Runs on the owner's phone in Termux, from an Iranian connection, and reads what GitHub's
runner cannot reach: Daric first (403 to the runner since 2026-10-03). Each reading goes to
Neon's HTTPS endpoint as one row of iran_node_readings; production reads it from there.

Needs only Python and requests. Settings live in ~/.iran_node.env, never in the repo:

    NEON_URL=postgresql://iran_node:<password>@<host>/neondb?sslmode=require
    NODE=s10

The iran_node role may only INSERT into iran_node_readings. When Neon cannot be reached the
reading waits in ~/iran_node_spool.jsonl and goes with the next run, so a cut of the
international link loses nothing.

    python node.py           read and send (cron runs this every 15 minutes)
    python node.py --test    read and print; send nothing
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

HOME = os.path.expanduser("~")
ENV_FILE = os.path.join(HOME, ".iran_node.env")
SPOOL = os.path.join(HOME, "iran_node_spool.jsonl")
LOG = os.path.join(HOME, "iran_node.log")
SPOOL_LIMIT = 3000          # about a month at four readings an hour

DARIC = "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice"
HEADERS = {"User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-G973F) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36",
           "Accept": "application/json"}

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


def main(argv):
    cfg = settings() if os.path.exists(ENV_FILE) else {}
    reading = dict(read_daric(), node=cfg.get("NODE", "s10"), observed_at=utc_now())
    summary = (f"daric {reading['status']} bid {reading['bid']:,.0f} ask {reading['ask']:,.0f}"
               if reading["status"] == "OK" else f"daric ERROR {reading['detail']}")
    if "--test" in argv:
        log(f"TEST {summary} (nothing sent)")
        return 0
    if "NEON_URL" not in cfg:
        log(f"no NEON_URL in {ENV_FILE}; {summary} kept in the spool")
        save_spool(load_spool() + [reading])
        return 1
    queue, unsent, failure = load_spool() + [reading], [], None
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
