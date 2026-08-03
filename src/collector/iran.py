"""Iranian market price collector with parallel execution and global timeout.

Collectors run concurrently via ThreadPoolExecutor.
Any collector still running after 25 seconds is cancelled.
"""

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from collector.milli import get_milli_price
from collector.goldika import get_goldika_price
from collector.wallgold import get_wallgold_price
from collector.taline import get_taline_price
from collector.hoorgold import get_hoorgold_price
from collector.parasteh import get_parasteh_price
from collector.ayyareh import get_ayyareh_price
from collector.miogold import get_miogold_price
from collector.eligallery import get_eligold_price
from collector.daric import get_daric_price

COLLECTORS = [
    get_milli_price,
    get_goldika_price,
    get_wallgold_price,
    get_taline_price,
    get_ayyareh_price,
    get_hoorgold_price,
    get_parasteh_price,
    get_miogold_price,
    get_daric_price,
    get_eligold_price,
]

# Hard ceiling: if a collector hangs, we stop waiting after this many seconds
GLOBAL_COLLECTOR_TIMEOUT = 20


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
    """Fetch all Iranian market prices in parallel with a global timeout.

    Returns a dict of {platform: {price, status}}.
    Any collector still running after GLOBAL_COLLECTOR_TIMEOUT seconds
    is cancelled and reported as timed out.
    """
    prices = {}
    pending = {}

    with ThreadPoolExecutor(max_workers=len(COLLECTORS)) as executor:
        # Submit all
        for c in COLLECTORS:
            future = executor.submit(_run_collector, c)
            pending[future] = c

        # Wait for all to finish, but cap total wall-clock time
        done, not_done = wait(
            pending.keys(),
            timeout=GLOBAL_COLLECTOR_TIMEOUT,
            return_when="ALL_COMPLETED",
        )

        # Collect completed results
        for future in done:
            name, info = future.result()
            prices[name] = info

        # Cancel anything still hanging
        for future in not_done:
            future.cancel()
            collector = pending[future]
            name = collector.__name__.replace("get_", "").replace("_price", "").title()
            prices[name] = {
                "price": None,
                "status": f"ERROR: collector timed out after {GLOBAL_COLLECTOR_TIMEOUT}s"
            }

    return prices
