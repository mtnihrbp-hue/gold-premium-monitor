from collectors.kitco import get_world_gold_price


def main():
    price = get_world_gold_price()
    print(f"World Gold Price: {price:.2f} USD/oz")


if __name__ == "__main__":
    main()
