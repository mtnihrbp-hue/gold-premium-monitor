def calculate_fair_price(world_gold_usd, usd_irr):
    """
    Returns the theoretical 18K gold price in IRR per gram.
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

    available = [
        info["price"]
        for info in prices.values()
        if info["status"] == "OK"
    ]

    return min(available)


def premium_percent(fair_price, market_price):

    return (market_price - fair_price) / fair_price * 100


def trading_signal(premium, buy_threshold, sell_threshold):

    if premium <= buy_threshold:
        return "BUY"

    if premium >= sell_threshold:
        return "SELL"

    return "HOLD"
