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
    "TRX": "Tron",
    # Token and second layer
    "ARB": "Arbitrum",
    "USDT": "Tether USD",
    "USDC": "Circle USD Coin",
}


KNOWN_NETWORKS = {
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
    "TRX": "Tron",
}

NETWORK_SUGGESTIONS = {
    "USDT": ["ETH", "ARB", "ETC", "BSC", "TRX"],
    "USDC": ["ETH", "ARB", "ETC", "BSC", "TRX"],
}


def suggest_networks_from_currency(currency, only_unknown=True):
    if currency in KNOWN_NETWORKS and not only_unknown:
        return [currency]
    return NETWORK_SUGGESTIONS.get(currency, [])


def is_known_network(network):
    return network in KNOWN_NETWORKS


def is_known_currency(currency):
    return currency in KNOWN_CURRENCIES
