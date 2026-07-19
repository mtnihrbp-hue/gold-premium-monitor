from collector.milli import get_milli_price
from collector.goldika import get_goldika_price
from collector.wallgold import get_wallgold_price
from collector.taline import get_taline_price


def get_market_prices():

    prices = {}

    collectors = [
        get_milli_price,
        get_goldika_price,
        get_wallgold_price,
        get_taline_price,
    ]

    for collector in collectors:
        try:
            result = collector()

            prices[result["platform"]] = {
                "price": result["price"],
                "status": "OK"
            }

        except Exception as e:

            name = collector.__name__.replace("get_", "").replace("_price", "").title()

            prices[name] = {
                "price": None,
                "status": f"ERROR: {e}"
            }

    return prices
