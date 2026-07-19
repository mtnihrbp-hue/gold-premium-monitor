from .milli import get_milli_price


def get_market_prices():

    prices = {}

    try:
        prices["Milli"] = get_milli_price()
    except Exception as e:
        print(f"Milli: {e}")

    if not prices:
        raise RuntimeError("No Iranian gold platform responded.")

    return prices
