from collector.relay import get_json

URL = "https://apisc.daric.gold/loan/api/v1/User/Collateral/GetGoldlPrice"


def get_daric_price():
    # Direct first; through the data relay when Daric refuses the runner (it answered 403
    # to foreign addresses on 4 of the 10 days to 2026-10-04; SP_D_HANDOFF.md section 10).
    data = get_json(URL, timeout=(5, 12))

    # Daric is an order book: BestSellPrice is the lowest offer (what a buyer pays),
    # BestBuyPrice the highest bid (what a seller is paid). Toman, hence x10.
    ask = float(data["Data"]["BestSellPrice"]) * 10
    bid = float(data["Data"]["BestBuyPrice"]) * 10
    return {
        "platform": "Daric",
        "price": ask,
        "buy": ask,
        "sell": bid,
    }
