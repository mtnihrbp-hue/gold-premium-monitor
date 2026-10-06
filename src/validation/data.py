"""Defensive validation for market data inputs.

Raises ValueError on invalid data so main.py can skip the run gracefully.
"""

from datetime import timedelta
from statistics import median

from timeutil import to_tehran


# These ranges catch garbage and unit slips, not unusual markets: a reading outside
# them is dropped (world gold falls back to a stored price for up to 6 hours, a
# platform is discarded). A ceiling the market can reach therefore stops the system
# at the moment the market makes news. Until 2026-10-06 world gold's was $5,000 with
# gold at $4,146, and 18K's 500M rial with 18K at 269M after a 70% rise in four months
# (SP_D_HANDOFF.md section 30).

# World gold, USD/oz. A price per gram (about $133) falls below the floor and one per
# kilogram (about $133,000) above the ceiling; the ceiling is 4.8 times 2026-10-06's.
MIN_WORLD_GOLD = 1000.0
MAX_WORLD_GOLD = 20000.0

# USD sell rate, in toman (bonbast; stored as market_snapshots.usd_irr, 269,300 on
# 2026-10-06). The ceiling also catches a rial slip (ten times the rate) for as long as
# the rate stays above 100,000; it is 3.7 times 2026-10-06's rate. Revisit when the rate
# passes 500,000.
MIN_USD_RATE = 10000.0
MAX_USD_RATE = 1000000.0

# Platform price, rial per gram of 18K. The ceiling, 500M toman, is 18.6 times
# 2026-10-06's price.
MIN_MARKET_PRICE = 1_000_000.0
MAX_MARKET_PRICE = 5_000_000_000.0

# Minimum number of working market sources for a valid signal
MIN_WORKING_SOURCES = 2

# Platforms whose published price can be a stale copy. Taline's price is read from a
# web page behind a CDN that, on 2026-09-29, served GitHub's non-Iranian runners copies
# up to a day old while serving Iran the live price (SP_C_HANDOFF.md 37.2). There is no
# public live source to read instead, so each quote is checked against the others.
STALE_PRONE_PLATFORMS = ("Taline",)

# Measured over 293 readings, 2026-09-15 to 09-29: Taline sits between -0.64% and
# +0.25% of the other platforms' median on 90% of readings, and its stale copies sat
# 1.0-3.6% away. A quote further than this is discarded for that reading, exactly as a
# failed collector is. Both sides are checked: in a falling market a stale copy sits
# above the others.
MAX_DEVIATION_FROM_OTHERS_PCT = 1.0

# The check needs enough other platforms to have a meaningful median. With fewer, the
# quote is kept; the decision engine's confirmation check still stops one platform
# from carrying a BUY on its own (SP_C_HANDOFF.md 38).
MIN_OTHERS_FOR_DEVIATION_CHECK = 3

# Any platform: a stale quote is deferred for the reading (owner, 2026-09-29: "if a
# platform is stale, it should be deferred"; 2026-10-02: "rectified once for all, it
# contaminates our DB"; SP_C_HANDOFF.md sections 39, 44). Three checks, from exact to
# inferred:
#
# 1. The source's own price time, where it publishes one (Goldika, Milli). A quote
#    priced longer ago than MAX_QUOTE_AGE_HOURS is a copy, not a price. On 2026-10-01
#    Goldika's CDN served the runner a copy priced 2026-09-13 for over a day.
#
# 2. The fingerprint and the drift, for every platform. Stale means both at once, so
#    that neither a genuine move nor a platform's natural position is mistaken for it:
#    - the exact price the platform already reported in an earlier reading, at least
#      STALE_MIN_AGE_HOURS ago and within STALE_LOOKBACK_DAYS -- a feed that stopped,
#      or a cache handing back an old copy;
#    - its distance from the other platforms' median differs from its own usual
#      distance (median over USUAL_OFFSET_DAYS) by more than STALE_DRIFT_PP. Platforms
#      sit at different places: Goldika about +1.1%, Milli about -0.9%.
#    Until 2026-10-02 the fingerprint looked only 3-48 hours back, so a new frozen
#    value passed for three hours, and a deferred one, never stored, slipped back in
#    once its last stored copy was 48 hours old.
#
# 3. A jump on first sight. A quote more than JUMP_HOLD_PP from its own usual position
#    is held until it is seen to move: a live price that has jumped keeps moving and
#    is accepted at the next reading; a copy or a stopped feed repeats and stays held.
#    Natural drift stays within about 1 pp; Taline's stale copies sat 4-5 pp away and
#    Goldika's 8.5 pp. Without it the first reading of a copy reached the push, the
#    decision engine and the stored record before any repeat could be seen.
MAX_QUOTE_AGE_HOURS = 6
STALE_MIN_AGE_HOURS = 0.75
STALE_LOOKBACK_DAYS = 60
USUAL_OFFSET_DAYS = 14
STALE_DRIFT_PP = 1.0
JUMP_HOLD_PP = 3.0
MIN_USUAL_OBSERVATIONS = 20


def validate_world_gold(price):
    """Validate world gold price."""
    if price is None:
        raise ValueError("World gold price is None")
    if not isinstance(price, (int, float)):
        raise ValueError(f"World gold price has invalid type: {type(price)}")
    if price <= 0:
        raise ValueError(f"World gold price must be positive, got {price}")
    if not (MIN_WORLD_GOLD <= price <= MAX_WORLD_GOLD):
        raise ValueError(
            f"World gold price out of range: {price} "
            f"(expected {MIN_WORLD_GOLD}-{MAX_WORLD_GOLD})"
        )
    return float(price)


def validate_usd_rate(rate):
    """Validate USD sell rate."""
    if rate is None:
        raise ValueError("USD rate is None")
    if not isinstance(rate, (int, float)):
        raise ValueError(f"USD rate has invalid type: {type(rate)}")
    if rate <= 0:
        raise ValueError(f"USD rate must be positive, got {rate}")
    if not (MIN_USD_RATE <= rate <= MAX_USD_RATE):
        raise ValueError(
            f"USD rate out of range: {rate} "
            f"(expected {MIN_USD_RATE}-{MAX_USD_RATE})"
        )
    return float(rate)


def defer_stale_quotes(valid, history, now, holds=None):
    """Find the quotes in `valid` that are stale copies or unseen jumps; remove them.

    `history` is (snapshot_id, timestamp, platform_name, price) for stored readings,
    `now` naive UTC. Every quote is judged against the same set of current prices
    before any is removed, so the outcome does not depend on the order of platforms.
    Without history nothing is deferred: a quote is never dropped on a guess, and the
    decision engine's confirmation check still stops one platform from carrying a
    signal.

    `holds` is {platform: price} carried between runs (state.json): the price a jumped
    quote had when last held. A jumped quote is accepted once it differs from that
    price, which is what a live price does and a copy does not. It is updated in place.
    Without it a jumped quote is held for as long as it stays jumped.

    Returns [(name, reason)] for what was removed.
    """
    if not history or now is None:
        return []

    snapshots = {}
    for snapshot_id, timestamp, name, price in history:
        if timestamp >= now:
            continue
        snapshots.setdefault(snapshot_id, (timestamp, {}))[1][name] = float(price)

    fresh_from = now - timedelta(days=STALE_LOOKBACK_DAYS)
    old_until = now - timedelta(hours=STALE_MIN_AGE_HOURS)
    usual_from = now - timedelta(days=USUAL_OFFSET_DAYS)

    deferred = []
    for name, info in valid.items():
        others_now = [float(other["price"]) for other_name, other in valid.items()
                      if other_name != name]
        if len(others_now) < MIN_OTHERS_FOR_DEVIATION_CHECK:
            continue
        price = float(info["price"])

        fingerprint = any(
            name in prices and abs(prices[name] - price) < 0.5
            and fresh_from <= timestamp <= old_until
            for timestamp, prices in snapshots.values()
        )

        offsets = []
        for timestamp, prices in snapshots.values():
            if name not in prices or timestamp < usual_from:
                continue
            others = [p for other_name, p in prices.items() if other_name != name]
            if len(others) >= MIN_OTHERS_FOR_DEVIATION_CHECK:
                offsets.append((prices[name] / median(others) - 1) * 100)
        if len(offsets) < MIN_USUAL_OBSERVATIONS:
            continue

        drift = (price / median(others_now) - 1) * 100 - median(offsets)
        if fingerprint and abs(drift) > STALE_DRIFT_PP:
            deferred.append((name, f"stale, a price it already reported in an earlier "
                                   f"reading, {drift:+.2f} pp from its usual position"))
            continue

        if abs(drift) <= JUMP_HOLD_PP:
            if holds is not None:
                holds.pop(name, None)
            continue
        held_at = holds.get(name) if holds is not None else None
        if holds is not None:
            holds[name] = price
        if held_at is not None and abs(held_at - price) >= 0.5:
            continue                    # it moved since it was held: a live price
        deferred.append((name, f"held, {drift:+.2f} pp from its usual position on first "
                               f"sight; accepted once it moves"))

    for name, _ in deferred:
        del valid[name]
    return deferred


def validate_market_prices(prices, history=None, now=None, holds=None):
    """Filter market prices, removing invalid / outlier entries.

    Prints a diagnostic line for each discarded platform.
    Returns a dict of only valid platforms.
    Raises ValueError if fewer than MIN_WORKING_SOURCES are available.

    `history` and `now` enable the stale-quote check (`defer_stale_quotes`); without
    them it is skipped. `now` also enables the source-time check for platforms that
    publish their price time. `holds` carries held jumps between runs.
    """
    if not prices:
        raise ValueError("No market price data received")

    print("\nVALIDATION")
    print("-" * 40)

    valid = {}
    discarded = 0

    for name, info in prices.items():
        reason = None

        if info.get("status") != "OK":
            reason = info.get("status", "unknown status")
        else:
            price = info.get("price")
            if price is None:
                reason = "price is None"
            elif not isinstance(price, (int, float)):
                reason = f"invalid type: {type(price).__name__}"
            elif price <= 0:
                reason = f"non-positive price: {price}"
            elif not (MIN_MARKET_PRICE <= price <= MAX_MARKET_PRICE):
                reason = f"price out of range: {price}"
            elif now is not None and info.get("quoted_at") is not None:
                age = (now - info["quoted_at"]).total_seconds() / 3600
                if age > MAX_QUOTE_AGE_HOURS:
                    reason = (f"stale, priced {to_tehran(info['quoted_at']):%Y-%m-%d %H:%M} "
                              f"Tehran, {age:.0f} h ago")

        if reason:
            print(f"  Discarded {name}: {reason}")
            discarded += 1
            continue

        valid[name] = info

    for name in STALE_PRONE_PLATFORMS:
        if name not in valid:
            continue
        others = [float(info["price"]) for other, info in valid.items() if other != name]
        if len(others) < MIN_OTHERS_FOR_DEVIATION_CHECK:
            continue
        deviation = (float(valid[name]["price"]) / median(others) - 1) * 100
        if abs(deviation) > MAX_DEVIATION_FROM_OTHERS_PCT:
            print(f"  Discarded {name}: stale copy suspected, "
                  f"{deviation:+.2f}% from the other platforms' median")
            del valid[name]
            discarded += 1

    for name, reason in defer_stale_quotes(valid, history, now, holds):
        print(f"  Deferred {name}: {reason}")
        discarded += 1

    print(f"  {len(valid)} valid source(s)")
    if discarded:
        print(f"  {discarded} discarded")

    if len(valid) < MIN_WORKING_SOURCES:
        raise ValueError(
            f"Only {len(valid)} valid market source(s). "
            f"Minimum required: {MIN_WORKING_SOURCES}"
        )

    return valid


def validate_fair_price(price):
    """Validate calculated fair price."""
    if price is None:
        raise ValueError("Fair price is None")
    if not isinstance(price, (int, float)):
        raise ValueError(f"Fair price has invalid type: {type(price)}")
    if price <= 0:
        raise ValueError(f"Fair price must be positive, got {price}")
    return float(price)


def classify_daily_candle(candle):
    """COMPLETE, INCONSISTENT or INVALID, for one external daily candle.

    INVALID (a price that is missing or not positive) is not a candle and is not
    stored. INCONSISTENT means the low and high do not bound the open and close: it is
    stored as the source published it, flagged, because correcting it would fabricate a
    price and dropping it would hide the source's own defect. tgju has 10 such candles
    in 7,480, most at a 100,000,000 / 1,000,000 Rial cap in September 2025.
    """
    prices = [candle.get(key) for key in ("open", "high", "low", "close")]
    if any(price is None or price <= 0 for price in prices):
        return "INVALID"
    open_, high, low, close = prices
    if low > min(open_, close) or high < max(open_, close):
        return "INCONSISTENT"
    return "COMPLETE"
