import os
import sys

sys.path.append(os.path.dirname(__file__))

from collector.kitco import get_world_gold_price
from collector.bonbast import get_usd_sell_rate


def main():

    world = get_world_gold_price()
    usd = get_usd_sell_rate()

    print(f"World Gold Price : {world:.2f} USD/oz")
    print(f"USD Sell Rate    : {usd:,} IRR")


if __name__ == "__main__":
    main()
