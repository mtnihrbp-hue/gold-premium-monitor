"""Iranian market price collector with parallel execution and a real global timeout.

Collectors run concurrently on daemon threads. Any collector still running after
GLOBAL_COLLECTOR_TIMEOUT seconds is abandoned and reported as timed out.

This previously used a ThreadPoolExecutor whose timeout did not bind. wait() was
capped correctly, but future.cancel() only cancels a future that has not started --
and with max_workers equal to the collector count, every future starts at once, so
nothing was ever cancellable. Leaving the `with` block then called shutdown(wait=True),
which blocks until the slowest thread finishes. The documented 20-second ceiling was
therefore followed immediately by an unbounded wait.

That is not theoretical: requests' timeout= does not bound DNS resolution, so a
degraded network leaves a collector thread hung indefinitely. Scheduled runs died
at the 20-minute job timeout having written nothing at all -- 2026-09-21 05:30 UTC
is one, and the hourly reading for that slot does not exist.

Daemon threads fix both halves: join() takes a real timeout, and the interpreter
does not wait for them at exit. A hung collector now costs one platform, not the run.
"""

import threading
import time

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
from collector.invi import get_invi_price

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
    get_invi_price,
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
    lock = threading.Lock()

    def runner(collector):
        name, info = _run_collector(collector)
        with lock:
            prices[name] = info

    threads = []
    for collector in COLLECTORS:
        thread = threading.Thread(target=runner, args=(collector,), daemon=True)
        thread.start()
        threads.append((thread, collector))

    # One shared deadline, not one timeout per join: eleven sequential joins of
    # GLOBAL_COLLECTOR_TIMEOUT each would allow eleven times the intended ceiling.
    deadline = time.monotonic() + GLOBAL_COLLECTOR_TIMEOUT
    for thread, _ in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))

    # A thread still alive is abandoned, not awaited. It is a daemon, so it cannot
    # hold the interpreter open, and its result would arrive too late to use.
    for thread, collector in threads:
        if thread.is_alive():
            name = collector.__name__.replace("get_", "").replace("_price", "").title()
            with lock:
                prices.setdefault(name, {
                    "price": None,
                    "status": f"ERROR: collector timed out after {GLOBAL_COLLECTOR_TIMEOUT}s",
                })

    return prices
