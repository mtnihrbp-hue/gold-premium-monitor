"""Iranian market price collector with parallel execution.

Collectors run concurrently via ThreadPoolExecutor.
Total time = slowest collector, not sum of all collectors.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from collector.milli import get_milli_price
from collector.goldika import get_goldika_price
from collector.wallgold import get_wallgold_price
from collector.taline import get_taline_price
from collector.hoorgold import get_hoorgold_price
from collector.parasteh import get_parasteh_price
from collector.ayyareh import get_ayyareh_price
from collector.miogold import get_miogold_price
from collector.eligallery import get_eligold_price

# Daric is excluded — frequent timeouts waste wall-clock time

COLLECTORS = [
    get_milli_price,
    get_goldika_price,
    get_wallgold_price,
    get_taline_price,
    get_ayyareh_price,
    get_hoorgold_price,
    get_parasteh_price,
    get_miogold_price,
    get_eligold_price,
]


def _run_collector(collector):
    """Run a single collector and return (name, result_dict)."""
    try:
        result = collector()
        return result["platform"], {
            "price": result["price"],
            "status": "OK"
        }
    except Exception as e:
        name = collector.__name__.replace("get_", "").replace("_price", "").title()
        return name, {
            "price": None,
            "status": f"ERROR: {e}"
        }


def get_market_prices():
    """Fetch all Iranian market prices in parallel.

    Returns a dict of {platform: {price, status}}.
    Total wall-clock time ≈ slowest collector (not sum).
    """
    prices = {}

    with ThreadPoolExecutor(max_workers=9) as executor:
        futures = {
            executor.submit(_run_collector, c): c
            for c in COLLECTORS
        }
        for future in as_completed(futures):
            name, info = future.result()
            prices[name] = info

    return prices
