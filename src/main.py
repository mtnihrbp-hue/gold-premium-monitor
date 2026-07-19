import os
import sys

sys.path.append(os.path.dirname(__file__))

from collector.kitco import get_world_gold_price
from collector.bonbast import get_usd_sell_rate
#from collector.iran import get_market_prices
from collector.milli import get_milli_price



def main():

    world = get_world_gold_price()
    usd = get_usd_sell_rate()
    #iran = get_market_prices()
    milli = get_milli_price()


    print(f"World Gold Price : {world:.2f} USD/oz")
    print(f"USD Sell Rate    : {usd:,} IRR")
    print()

    print("Iranian Platforms")

    for platform, price in milli.items()
        print(f"{platform:<10} {price:,}")
    #for platform, price in iran.items():
     #   print(f"{platform:<10} {price:,}")


if __name__ == "__main__":
    main()
