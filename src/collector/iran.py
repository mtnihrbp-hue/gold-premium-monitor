from collector.milli import get_milli_price
from collector.goldika import get_goldika_price
from collector.daric import get_daric_price
from collector.wallgold import get_wallgold_price


def get_market_prices():
    prices = {}

    collectors = [
        get_milli_price,
        get_goldika_price,
        get_daric_price,
        get_wallgold_price,
    ]

    for collector in collectors:
        try:
            result = collector()
            prices[result["platform"]] = result["price"]
        except Exception as e:
            print(f"{collector.__name__}: {e}")

    if not prices:
        raise RuntimeError("No Iranian gold platform responded.")

    return prices
