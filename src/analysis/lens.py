"""The nightly lens (SP_D_HANDOFF.md sections 84-86), computed: every number and every flag the message prints.
alerts/telegram_lens.py only formats it.

- **Now, against the last close:** 18K from the platforms at tgju's level (the price Direction shows), world gold
  and the dollar as the run read them, Tether from tgju; each against tgju's close of the last trading day
  before today; and 18K against its world price then and now.
- **The event:** the ceasefire's odds from Polymarket, the two shown (the first date two days out or more, the
  last within two weeks) with their previous reading; the day's headlines picked and translated by the model.
- **What followed before:** the case library's strikes and deals against any day.
- **The read:** three flags, each from the numbers above, never from the model.
Network reads fail one at a time; the message says what was not read."""

from datetime import date, timedelta

from analysis import cases as case_library
from caluclator.gold import calculate_fair_price

ODDS_SOON, ODDS_FAR = 2, 14       # days ahead: the first odds shown and the last
DRIVER_RATIO, DRIVER_MIN = 2.0, 0.5
SHUT_BREAK_ODDS = 0.15            # the caution about a shut market, when a break is this likely


def pct(now, then):
    return (now / then - 1) * 100 if now and then else None


def _on_or_before(candles, day):
    rows = [c for c in candles or () if c.get("date") and c["date"] <= day and c.get("close")]
    return max(rows, key=lambda c: c["date"]) if rows else None


def market_now(price, world, usd, candles, today):
    """Now against tgju's last close before `today` (ISO). `candles` maps tgju's keys to their daily rows."""
    ref = _on_or_before([c for c in candles.get("geram18") or () if c.get("date", "") < today], "9999")
    if ref is None:
        return None
    day = ref["date"]
    w0, u0, t0 = (_on_or_before(candles.get(k), day) for k in ("ons", "price_dollar_rl", "crypto-tether-irr"))
    tether = max((c for c in candles.get("crypto-tether-irr") or () if c.get("close")), key=lambda c: c["date"],
                 default=None)
    history = [c["close"] for c in candles.get("tether_history") or () if c.get("close") and tether
               and c["date"] < tether["date"]]
    fair_now = calculate_fair_price(world, usd) if world and usd else None
    fair_then = calculate_fair_price(w0["close"], u0["close"]) if w0 and u0 else None
    return {"ref_date": day, "price": price, "world": world, "usd": usd,
            "tether": tether["close"] if tether else None,
            "price_pct": pct(price, ref["close"]), "world_pct": pct(world, w0 and w0["close"]),
            "usd_pct": pct(usd, u0 and u0["close"]), "tether_pct": pct(tether and tether["close"], t0 and t0["close"]),
            "tether_record": bool(tether and history and tether["close"] > max(history)),
            "gap_now": pct(price, fair_now), "gap_then": pct(ref["close"], fair_then)}


def odds_view(odds, previous, today):
    """The two ceasefire readings shown, each (end date, holds, was), and what to keep for tomorrow."""
    soon = [o for o in odds if o[0] >= today + timedelta(days=ODDS_SOON)]
    far = [o for o in soon if o[0] <= today + timedelta(days=ODDS_FAR)]
    shown = []
    if far:
        shown = [far[0]] + ([far[-1]] if far[-1][0] != far[0][0] else [])
    elif soon:
        shown = [soon[0]]
    view = [(end, holds, (previous or {}).get(end.isoformat())) for end, holds, _ in shown]
    return view, {end.isoformat(): holds for end, holds, _ in odds}


def read_flags(market, odds_shown, strikes):
    """The read, from the numbers: which leg moved 18K today, and the cases' direction and the shut market."""
    flags = {}
    if market and market["world_pct"] is not None and market["usd_pct"] is not None:
        w, u = abs(market["world_pct"]), abs(market["usd_pct"])
        if w >= DRIVER_MIN and w >= DRIVER_RATIO * u:
            flags["driver"] = "world"
        elif u >= DRIVER_MIN and u >= DRIVER_RATIO * w:
            flags["driver"] = "dollar"
    if strikes:
        flags["strikes_usual"] = strikes["usual_direction"]
        flags["strikes_bigger"] = strikes["bigger"]
        breaks = max((1 - holds for _, holds, _ in odds_shown), default=0)
        flags["shut_caution"] = bool(strikes["shut"]) and breaks >= SHUT_BREAK_ODDS
    return flags


def build_view(markets, world, usd, now, previous_odds=None, fetch_candles=None, fetch_odds=None, news=None):
    """Everything the lens prints, read now. The fetchers default to tgju, Polymarket, the channels and Groq."""
    from analysis.direction import live_gold_price
    from timeutil import local_date, local_now

    today = local_date(now)
    if fetch_candles is None:
        from collector.tgju import fetch_daily_candles

        def fetch_candles():
            out = {}
            for key, rows in (("geram18", 6), ("ons", 6), ("price_dollar_rl", 6), ("crypto-tether-irr", 6),
                              ("tether_history", 2500)):
                try:
                    out[key] = fetch_daily_candles("crypto-tether-irr" if key == "tether_history" else key, rows=rows)
                except Exception as e:  # noqa: BLE001 -- the line is left out
                    print(f"LENS: tgju {key} not read: {type(e).__name__}")
            return out
    if fetch_odds is None:
        from collector.polymarket import ceasefire_odds as fetch_odds
    if news is None:
        from intelligence import news_lens

        def news():
            heads = news_lens.day_headlines(now)
            return news_lens.read(heads), len(heads)
    market = market_now(live_gold_price(markets), world, usd, fetch_candles(), today.isoformat())
    odds_shown, odds_state = odds_view(fetch_odds(now), previous_odds, today)
    picks, headlines = news()
    seed = case_library.load()
    strikes, deals = case_library.summary(seed, "strike"), case_library.summary(seed, "deal")
    return {"at": local_now(now), "market": market, "odds": odds_shown, "odds_state": odds_state,
            "news": picks, "headlines": headlines, "strikes": strikes, "deals": deals,
            "base": seed["base"], "first_case": min(c["date"] for c in seed["cases"]),
            "flags": read_flags(market, odds_shown, strikes)}
