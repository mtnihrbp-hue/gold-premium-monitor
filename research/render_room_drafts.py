"""The room's messages, drafted on real data for the owner's review (SP-D, 2026-10-05).

tgju's stored history (research/data/tgju_history.json) in a scratch database, the room's account
started on 1403/07/14 (2024-10-05), its posture replayed day by day through production's own code
(main._room_state, analysis.room, analysis.paper.room_trade), quotes at Daric's 0.30% round trip
around tgju's close, Afran at its own close (src/seed). Prints every trade the room would have made,
the push it would have sent for the 1405 ones, and today's 21:00 report. Nothing is sent.
"""
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import main  # noqa: E402
from alerts.telegram_paper import build_room_report_message, build_room_trade_message  # noqa: E402
from analysis import paper, room  # noqa: E402
from database.connection import Base  # noqa: E402
from database.models import MarketDailyCandle  # noqa: E402
from database.repository import ensure_paper_accounts  # noqa: E402
from timeutil import persian_quarter  # noqa: E402

T = json.load(open(os.path.join(HERE, "data", "tgju_history.json")))
engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine, expire_on_commit=False)
s = Session()
for key, name in (("geram18", "TGJU_GOLD_18K"), ("price_dollar_rl", "TGJU_USD_IRR"), ("ons", "TGJU_XAU_USD")):
    for r in T[key]:
        s.add(MarketDailyCandle(source="tgju", instrument=name, trade_date=date.fromisoformat(r["date"]), open=r["open"],
                                high=r["high"], low=r["low"], close=r["close"], unit="IRR", source_quality="COMPLETE",
                                collected_at=datetime(2026, 10, 5)))
s.add(MarketDailyCandle(source="tablokhani", instrument="AFRAN_LAST", trade_date=date(2026, 10, 4), open=54490, high=54490,
                        low=54490, close=54490, unit="IRR", source_quality="LAST_KNOWN", collected_at=datetime(2026, 10, 5)))
s.commit()
start_utc = datetime(2024, 10, 5, 3, 31)
accounts = ensure_paper_accounts(s, paper.ACCOUNTS, paper.START_CASH_IRR, paper.VENUE_LABEL, start_utc)
close = [float(r["close"]) for r in T["geram18"]]
quant = main._quant_view(s, accounts, close, date(2026, 10, 5))
state = main._room_state(s, accounts[paper.ROOM], quant)
fi_seed = json.load(open(os.path.join(HERE, "..", "src", "seed", "fixed_income.json")))
scale = fi_seed["afran_scale"]
fi_days = sorted(state["fi"])


def afran(day):
    from bisect import bisect_right
    k = fi_days[bisect_right(fi_days, day) - 1]
    return state["fi"][k] / scale


dates, c = state["dates"], state["close"]
book = paper.Book(float(paper.START_CASH_IRR), 0)
hold = paper.Book(float(paper.START_CASH_IRR), 0)
values, hold_values, trades = {}, {}, []
for i in range(state["start"], len(dates)):
    day = dates[i]
    q = paper.Quote("Daric", c[i] * 1.0015, c[i] * 0.9985)
    posture = state["path"][i - state["start"]]["posture"]
    before = book
    d, book = paper.room_trade(book, q, posture, afran(day), 0)
    if d.action in ("BUY", "SELL"):
        trades.append((i, d, book, before, q))
    if hold.grams == 0:
        g = int(hold.cash // q.buy)
        hold = paper.Book(hold.cash - g * q.buy, g)
    values[day] = book.value(q.sell, afran(day))
    hold_values[day] = hold.value(q.sell)


def quarter_base(day, series):
    first = persian_quarter(day)[0]
    earlier = [k for k in series if k < first]
    return (series[max(earlier)] if earlier else float(paper.START_CASH_IRR)), first


plain = lambda html: re.sub(r"</?[bi]>", "", html)
print("Every trade the room would have made (from 1403/07/14):")
for i, d, after, before, q in trades:
    print(f"   {state['dates'][i]} {d.action:4} {d.grams} g -> {after.grams} g in gold, {after.units:,.0f} Afran units")
print(f"\nThe two years: the room {values[dates[-1]] / 1e7:.1f}M against holding {hold_values[dates[-1]] / 1e7:.1f}M")

print("\n" + "=" * 60 + "\nDRAFT 1 and 2: the pushes, as the room would have sent them in 1405\n" + "=" * 60)
for i, d, after, before, q in trades:
    if dates[i] < date(2026, 3, 21):
        continue
    view = main._room_view_at(state, i)
    at = datetime.combine(dates[i], time(3, 31))          # the 07:01 Tehran run
    msg = build_room_trade_message(d.action, d.grams, d.price, q.venue, at, view, after, afran(dates[i]), False, q.sell,
                                   quarter_base(dates[i], values), before.units)
    print("\n" + plain(msg))

print("\n" + "=" * 60 + "\nDRAFT 3: tonight's 21:00 report, on today's real data\n" + "=" * 60)
i = len(dates) - 1
view = main._room_view_at(state, i)
q = paper.Quote("Daric", c[i] * 1.0015, c[i] * 0.9985)
base, base_day = quarter_base(dates[i], values)
hbase, _ = quarter_base(dates[i], hold_values)
msg = build_room_report_message(date(2026, 10, 5), "Daric", q.sell, "", book.grams, book.units, afran(dates[i]), False,
                                values[dates[i]], base, base_day, (hold_values[dates[i]], hbase), [], view)
print("\n" + plain(msg))
print("\n(the room's evidence today: " + ", ".join(f"{m} {v:+d}" for m, v in view["members"].items())
      + f"; stocks {view['stocks']:+d}; share for fixed income {view['share']:.0%})")
print("chart reading: " + " | ".join(view["chart"]))
