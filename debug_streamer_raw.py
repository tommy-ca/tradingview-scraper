import logging

from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

# Enable debug logging
logging.basicConfig(level=logging.INFO)


def debug_sync(symbol):
    print(f"\n--- Debugging {symbol} ---")
    loader = PersistentDataLoader()
    added = loader.sync(symbol, interval="1d", depth=500)
    print(f"Added records: {added}")


if __name__ == "__main__":
    debug_sync("BINANCE:BTCUSDT")
    debug_sync("BINANCE:ETHUSDT")
    debug_sync("BINANCE:SOLUSDT")
