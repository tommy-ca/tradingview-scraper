import logging

from tradingview_scraper.symbols.screener import Screener

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_scanner")


def debug_spot():
    s = Screener()
    filters = [
        {"left": "exchange", "operation": "equal", "right": "BINANCE"},
        {"left": "type", "operation": "equal", "right": "spot"},
        {"left": "Value.Traded", "operation": "greater", "right": 10000000},
        {"left": "Volatility.D", "operation": "greater", "right": 1},
    ]
    columns = ["name", "Value.Traded", "Volatility.D", "Recommend.All", "Recommend.All|240"]

    logger.info("Executing Spot Scan ($10M floor, >1% Vol)...")
    res = s.screen(market="crypto", filters=filters, columns=columns)
    data = res.get("data", [])
    logger.info(f"Results found: {len(data)}")

    if data:
        data.sort(key=lambda x: x.get("Recommend.All|240") or -2, reverse=True)
        for i, r in enumerate(data[:10]):
            logger.info(f"#{i + 1}: {r['symbol']} | 4h Rating: {r.get('Recommend.All|240'):.4f} | Vol: {r.get('Volatility.D'):.2f}% | Value: ${r.get('Value.Traded') / 1e6:.1f}M")


def debug_perp():
    s = Screener()
    filters = [
        {"left": "exchange", "operation": "equal", "right": "BINANCE"},
        {"left": "type", "operation": "equal", "right": "swap"},
        {"left": "Value.Traded", "operation": "greater", "right": 50000000},
        {"left": "Volatility.D", "operation": "greater", "right": 1},
    ]
    columns = ["name", "Value.Traded", "Volatility.D", "Recommend.All", "Recommend.All|240"]

    logger.info("\nExecuting Perp Scan ($50M floor, >1% Vol)...")
    res = s.screen(market="crypto", filters=filters, columns=columns)
    data = res.get("data", [])
    logger.info(f"Results found: {len(data)}")

    if data:
        data.sort(key=lambda x: x.get("Recommend.All|240") or -2, reverse=True)
        for i, r in enumerate(data[:10]):
            logger.info(f"#{i + 1}: {r['symbol']} | 4h Rating: {r.get('Recommend.All|240'):.4f} | Vol: {r.get('Volatility.D'):.2f}% | Value: ${r.get('Value.Traded') / 1e6:.1f}M")


if __name__ == "__main__":
    debug_spot()
    debug_perp()
