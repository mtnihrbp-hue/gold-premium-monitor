from .milli import get_milli_price
from .goldika import get_goldika_price
from .daric import get_daric_price
from .wallgold import get_wallgold_price
from .taline import get_taline_price


def get_market_prices():
    prices = {}

    collectors = [
        ("Milli", get_milli_price),
        ("Goldika", get_goldika_price),
        ("Daric", get_daric_price),
        ("WallGold", get_wallgold_price),
        ("Taline", get_taline_price),
    ]

    for name, collector in collectors:
        try:
            prices[name] = collector()
        except Exception as e:
            print(f"{name}: {e}")

    if not prices:
        raise RuntimeError("No Iranian gold platform responded.")

    return prices
