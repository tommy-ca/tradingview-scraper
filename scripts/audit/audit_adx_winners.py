import pandas as pd
import logging
# from tradingview_scraper.symbols.stream.lakehouse import LakehouseLoader # Not needed if reading parquet directly

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit_adx_winners")

# Target symbols (ADX Winners)
SYMBOLS = ["BINANCE:ROSEUSDT", "BINANCE:DUSKUSDT", "BINANCE:ZROUSDT"]


def audit_sma_failure():
    logger.info(f"Auditing SMA Regime for: {SYMBOLS}")

    for symbol in SYMBOLS:
        try:
            # Load Feature Matrix via Persistent Loader or direct parquet read?
            # LakehouseLoader reads prices. We need features.
            # Let's read the features matrix directly.

            # Note: Feature matrix is partitioned or single file?
            # It's 'data/lakehouse/features_matrix.parquet'

            # We can't easily read just one symbol from parquet without reading all or using filter
            # Let's read the whole thing, it's not huge yet (2000 rows, 1500 cols)

            # OR we can calculate SMA on the fly from price history to be sure.
            # Let's read features first.

            df = pd.read_parquet("data/lakehouse/features_matrix.parquet")

            # MultiIndex columns: (symbol, feature)
            if symbol not in df.columns.get_level_values(0):
                logger.error(f"{symbol} not found in feature matrix.")
                continue

            sma_200 = df[(symbol, "sma_200")].iloc[-1]
            vwma_20 = df[(symbol, "vwma_20")].iloc[-1]

            # We need Close too. Backfill puts SMA but maybe not Close?
            # But we can infer Close from VWMA ~ Close.
            # Or fetch price history.

            price_df = pd.read_parquet(f"data/lakehouse/{symbol.replace(':', '_')}_1d.parquet")
            close = price_df["close"].iloc[-1]

            logger.info(f"--- {symbol} ---")
            logger.info(f"Close: {close:.4f}")
            logger.info(f"SMA200: {sma_200:.4f}")
            logger.info(f"VWMA20: {vwma_20:.4f}")

            # SMA Filter Logic (Long)
            is_bull = close > sma_200
            logger.info(f"Regime (Bull): {is_bull} (Close > SMA200)")

            # Crossover Check
            # Need history

        except Exception as e:
            logger.error(f"Error auditing {symbol}: {e}")


if __name__ == "__main__":
    audit_sma_failure()
