"""Defensive validation for market data inputs.

Raises ValueError on invalid data so main.py can skip the run gracefully.
"""


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


def validate_market_prices(prices):
    """Filter market prices, removing invalid / outlier entries.

    Prints a diagnostic line for each discarded platform.
    Returns a dict of only valid platforms.
    Raises ValueError if fewer than MIN_WORKING_SOURCES are available.
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
