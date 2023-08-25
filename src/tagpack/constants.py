KNOWN_CURRENCIES = {
    # Base currencies
    "ETH": "Ether",
    "BTC": "Bitcoin",
    "XBT": "Bitcoin ISO 4217",
    "BCH": "Bitcoin Cash",
    "ZEC": "Z-Cash",
    "LTC": "Litecoin",
    "WETH": "Wrapped Ether",
    "XMR": "Monero",
    "DASH": "Dash",
    "BTG": "Bitcoin Gold",
    "ETC": "Ethereum Classic",
    "BSV": "Bitcoin Satoshi Vision",
    "XRP": "Ripple",
    # Token and second layer
    "ARB": "Arbitrum",
    "USDT": "Tether USD",
    "USDC": "Circle USD Coin",
}


KNOWN_CHAINS = {
    "ETH": "Ethereum",
    "BTC": "Bitcoin",
    "BCH": "Bitcoin Cash",
    "ZEC": "Z-Cash",
    "LTC": "Litecoin",
    "BSC": "Binance Smartchain",
    "XMR": "Monero",
    "DASH": "Dash",
    "BTG": "Bitcoin Gold",
    "ETC": "Ethereum Classic",
    "BSV": "Bitcoin Satoshi Vision",
    "XRP": "Ripple",
    "ARB": "Arbitrum",
}

CHAIN_SUGGESTIONS = {
    "USDT": ["ETH", "ARB", "ETC", "BSC"],
    "USDC": ["ETH", "ARB", "ETC", "BSC"],
}


def suggest_chains_from_currency(currency, only_unknown=True):
    if currency in KNOWN_CHAINS and not only_unknown:
        return [currency]
    return CHAIN_SUGGESTIONS.get(currency, [])


def is_known_chain(chain):
    return chain in KNOWN_CHAINS


def is_known_currency(currency):
    return currency in KNOWN_CURRENCIES
