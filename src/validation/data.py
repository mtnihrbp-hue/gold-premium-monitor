"""Defensive validation for market data inputs.

Raises ValueError on invalid data so main.py can skip the run gracefully.
"""

from datetime import timedelta
from statistics import median


# World gold price reasonable range: $1000 – $5000 USD/oz
MIN_WORLD_GOLD = 1000.0
MAX_WORLD_GOLD = 5000.0

# USD/IRR reasonable range: 10,000 – 1,000,000 IRR
MIN_USD_RATE = 10000.0
MAX_USD_RATE = 1000000.0

# Market price reasonable range: 1M – 500M IRR per gram 18K
MIN_MARKET_PRICE = 1_000_000.0
MAX_MARKET_PRICE = 500_000_000.0

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
# platform is stale, it should be deferred"; SP_C_HANDOFF.md section 39). Stale means
# both of these at once, so that neither a genuine price move nor a platform's natural
# position is mistaken for staleness:
#
# - the fingerprint: the exact price the platform already reported between 3 and 48
#   hours ago -- a feed that never moved, or a cache handing back an old copy;
# - the market has moved away from it: its distance from the other platforms' median
#   differs from its own usual distance by more than 1.0 pp. Usual means the median
#   over 14 days, because platforms sit at different places: Goldika about +1.1%,
#   Milli about -0.9%.
#
# Replayed over 2026-09-15..29 this defers 27 of about 3,150 platform readings (0.9%):
# Taline 14 (its stale episodes), HoorGold 8 (mostly around 10:00, when the others
# have repriced and it has not), MioGold 5 -- and keeps MioGold's 14 genuine large
# moves, which carry new prices, and the natural offsets of Goldika and Milli.
STALE_MIN_AGE_HOURS = 3
STALE_MAX_AGE_HOURS = 48
USUAL_OFFSET_DAYS = 14
STALE_DRIFT_PP = 1.0
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


def defer_stale_quotes(valid, history, now):
    """Find the quotes in `valid` that are stale copies, and remove them.

    `history` is (snapshot_id, timestamp, platform_name, price) for stored readings,
    `now` naive UTC. Every quote is judged against the same set of current prices
    before any is removed, so the outcome does not depend on the order of platforms.
    Without history nothing is deferred: a quote is never dropped on a guess, and the
    decision engine's confirmation check still stops one platform from carrying a
    signal. Returns [(name, reason)] for what was deferred.
    """
    if not history or now is None:
        return []

    snapshots = {}
    for snapshot_id, timestamp, name, price in history:
        if timestamp >= now:
            continue
        snapshots.setdefault(snapshot_id, (timestamp, {}))[1][name] = float(price)

    fresh_from = now - timedelta(hours=STALE_MAX_AGE_HOURS)
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
        if not fingerprint:
            continue

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
        if abs(drift) > STALE_DRIFT_PP:
            deferred.append((name, f"stale, the same price as {STALE_MIN_AGE_HOURS}h+ ago "
                                   f"and {drift:+.2f} pp from its usual position"))

    for name, _ in deferred:
        del valid[name]
    return deferred


def validate_market_prices(prices, history=None, now=None):
    """Filter market prices, removing invalid / outlier entries.

    Prints a diagnostic line for each discarded platform.
    Returns a dict of only valid platforms.
    Raises ValueError if fewer than MIN_WORKING_SOURCES are available.

    `history` and `now` enable the stale-quote check (`defer_stale_quotes`); without
    them it is skipped.
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

    for name, reason in defer_stale_quotes(valid, history, now):
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
