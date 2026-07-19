
from collector.milli import get_milli_price


def get_market_prices():
    prices = []

    try:
        prices.append(get_milli_price())
    except Exception as e:
        print("Milli:", e)

    if not prices:
        raise RuntimeError("No Iranian gold platform responded.")

    return prices
