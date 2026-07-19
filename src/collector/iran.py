from collector.milli import get_milli_price


def get_market_prices():
    milli = get_milli_price()

    return {
        milli["platform"]: milli["price"]
    }
