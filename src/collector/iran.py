from collector.milli import get_milli_price
from collector.goldika import get_goldika_price
from collector.wallgold import get_wallgold_price
from collector.taline import get_taline_price
from collector.hoorgold import get_hoorgold_price
from collector.parasteh import get_parasteh_price
from collector.daric import get_daric_price
from collector.ayyareh import get_ayyareh_price
from collector.miogold import get_miogold_price
from collector.eligallery import get_eligold_price


def get_market_prices():

    prices = {}

    collectors = [
        get_milli_price,
        get_goldika_price,
        get_wallgold_price,
        get_taline_price,
        get_ayyareh_price,
        get_hoorgold_price,
        get_parasteh_price,
        get_miogold_price,
        get_eligold_price,
        get_daric_price,
        
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
