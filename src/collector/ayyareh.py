import requests

URL = "https://ayyareh.com/general/getGoldPrice.php"


def get_ayyareh_price():
    response = requests.get(URL, timeout=10)
    response.raise_for_status()

    data = response.json()
    price = float(data["goldPrice"]) * 10

    result = {
        "platform": "Ayyareh",
        "price": price,
    }
    # Ayyareh publishes one price and a fee on each side ("buyWageValue" and
    # "sellWageValue": 0.02 at 10:35 and 0.01 at 11:57 on 2026-10-04). A buyer pays the
    # price plus the buy fee, a seller is paid the price less the sell fee. `price` stays
    # the published one, as every other consumer reads it (SP_D_HANDOFF.md section 10).
    buy_fee, sell_fee = data.get("buyWageValue"), data.get("sellWageValue")
    if buy_fee is not None and sell_fee is not None:
        result["buy"] = price * (1 + float(buy_fee))
        result["sell"] = price * (1 - float(sell_fee))
    return result
