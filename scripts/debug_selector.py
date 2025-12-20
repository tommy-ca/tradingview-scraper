import logging

from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, load_config

logging.basicConfig(level=logging.INFO)


def debug_binance():
    config = load_config("configs/crypto_cex_base_top50_binance.yaml")
    # Disable trend filters for broad review
    config.trend.recommendation.enabled = False
    config.trend.adx.enabled = False
    config.trend.momentum.enabled = False
    config.limit = 100

    selector = FuturesUniverseSelector(config)
    data = selector.run()
    print(f"Status: {data['status']}")
    print(f"Total Found: {len(data.get('data', []))}")
    if data.get("errors"):
        print(f"Errors: {data['errors']}")


if __name__ == "__main__":
    debug_binance()
