def calculate_fair_price(world_gold_usd, usd_irr):
    """Theoretical 18K gold price per gram, in the same currency unit as `usd_irr`.

    The unit is inherited, not fixed. bonbast reports USD in Tomans, so with a
    Toman rate this returns Tomans -- despite the name of the argument. The only
    production caller multiplies the result by 10 to reach Rials, which is the unit
    every persisted price uses.

    The previous docstring claimed IRR, which was wrong by a factor of ten and would
    mislead any second caller. Correcting the text rather than relocating the
    conversion is deliberate: `market_snapshots.fair_price` has always been stored
    Rial-scale from the corrected call site, so moving the multiplication is a change
    to stored-value semantics and needs its own phase, like the premium_percent basis
    split. See SP_C_HANDOFF.md 15.1.
    """

    PURE_GOLD_GRAMS_PER_OUNCE = 31.1034768
    GOLD_PURITY = 0.750

    return (
        world_gold_usd
        * usd_irr
        / PURE_GOLD_GRAMS_PER_OUNCE
        * GOLD_PURITY
    )


def find_lowest_market_price(prices):
    available = [info["price"] for info in prices.values() if info["status"] == "OK"]
    if not available:
        return None
    return min(available)


def premium_percent(fair_price, market_price):
    if fair_price == 0:
        return 0.0
    return (market_price - fair_price) / fair_price * 100


def trading_signal(premium, buy_threshold, sell_threshold):

    if premium <= buy_threshold:
        return "BUY"

    if premium >= sell_threshold:
        return "SELL"

    return "HOLD"
