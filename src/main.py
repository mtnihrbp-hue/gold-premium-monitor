import os
import sys

sys.path.append(os.path.dirname(__file__))

from collectors.kitco import get_world_gold_price
from collectors.bonbast import get_usd_sell_rate


def main():
    gold = get_world_gold_price()
    usd = get_usd_sell_rate()

    print(f"World Gold Price : {gold:.2f} USD/oz")
    print(f"USD Sell Rate    : {usd:,.0f} IRR")


if __name__ == "__main__":
    main()
