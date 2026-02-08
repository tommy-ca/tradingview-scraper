import logging

from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, load_config

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("inspect_scanner")


def inspect(config_path: str):
    logger.info(f"Inspecting scanner: {config_path}")
    cfg = load_config(config_path)
    selector = FuturesUniverseSelector(cfg)

    columns = selector._build_columns()
    payloads = selector.build_payloads(columns=columns)

    aggregated = []
    for payload in payloads:
        market_rows, market_errors = selector._screen_market(
            payload["market"],
            payload["filters"],
            payload["columns"],
            exchange=payload.get("exchange"),
            max_rows=100,
        )
        logger.info(f"Raw results from {payload['market']} ({payload.get('exchange')}): {len(market_rows)}")
        aggregated.extend(market_rows)

    if not aggregated:
        logger.error("No data returned from TradingView Screener API.")
        return

    result = selector.process_data(aggregated)
    logger.info(f"Final Count: {result.get('total_selected')}")
    if result.get("data"):
        for r in result["data"][:15]:
            logger.info(
                f"Selected: {r.get('symbol')} | 1d: {float(r.get('Recommend.All') or 0):.2f} | 4h: {float(r.get('Recommend.All|240') or 0):.2f} | Vol: {float(r.get('Volatility.D') or 0):.2f}%"
            )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        inspect(sys.argv[1])
    else:
        inspect("configs/scanners/crypto/ratings/binance_spot_rating_all_long.yaml")
