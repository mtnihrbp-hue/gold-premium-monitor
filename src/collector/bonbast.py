from bonbast import Bonbast


def get_usd_sell_rate() -> float:
    """
    Returns USD sell rate in IRR.
    """
    client = Bonbast()

    usd = client.currency("USD")

    return float(usd.sell)
