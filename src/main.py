from collector.kitco import get_world_gold_price
from collector.bonbast import get_usd_sell_rate
from collector.iran import get_market_prices

from caluclator.gold import (
    calculate_fair_price,
    find_lowest_market_price,
    premium_percent,
)


def main():

    world = get_world_gold_price()
    usd = get_usd_sell_rate()
    iran = get_market_prices()

    fair = calculate_fair_price(world, usd)
    lowest = find_lowest_market_price(iran)
    premium = premium_percent(fair, lowest)

    print(f"World Gold Price : {world:.2f} USD/oz")
    print(f"USD Sell Rate    : {usd:,} IRR")
    print()

    print("Iranian Platforms")
    print("-" * 45)

    for platform, info in iran.items():

        if info["status"] == "OK":
            print(f"{platform:<12} {info['price']:>15,.0f}")
        else:
            print(f"{platform:<12} ERROR")

    print("-" * 45)
    print()

    print(f"Fair Price      : {fair:,.0f}")
    print(f"Lowest Market   : {lowest:,.0f}")
    print(f"Premium         : {premium:.2f}%")


if __name__ == "__main__":
    main()
