"""The two kinds of platform (owner, 2026-10-29; SP_D_HANDOFF.md sections 64-65).

The owner: "there are two types of platforms here: one that you can buysell gold in form of gold grams. no gold
product. the other is for gold products, like bracelets rings and so on ... sometimes, you are at the bazar
wanting to buy a gold ring, so you need to see what normally the gold product platforms are buying selling."

- **Gold grams:** Milli, Goldika, WallGold, Taline, Ayyareh, Daric, Invi.
- **Gold products:** a jewellery gallery's 18K price, frozen 17% to 61% of the time on the record (63.3).

The discount, its 30-day record, the deep-discount level, the push and the BUY confirmation rest on the gram
platforms. The product platforms are shown apart, as the bazaar's reference.

`market_snapshots.premium_percent` keeps every platform's single cheapest, as stored since July: it is the
parked BUY engine's input, and changing it would split its series.

One definition here, as `timeutil` holds the time and `tolerances` the bands.
"""

PRODUCT_PLATFORMS = frozenset({"Eligold", "HoorGold", "Parasteh", "MioGold"})


def is_gram(name):
    """True for a platform where gold is bought and sold as grams."""
    return name not in PRODUCT_PLATFORMS


def gram_markets(markets):
    """The gram platforms of a {name: info} reading."""
    return {name: info for name, info in (markets or {}).items() if is_gram(name)}


def product_markets(markets):
    """The gold-product platforms of a {name: info} reading."""
    return {name: info for name, info in (markets or {}).items() if not is_gram(name)}
