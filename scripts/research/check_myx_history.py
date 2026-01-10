import logging

import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("check_myx")


def check_history():
    df = pd.read_pickle("data/lakehouse/portfolio_returns.pkl")
    symbol = "BINANCE:MYXUSDT.P"

    if symbol in df.columns:
        valid_days = df[symbol].count()
        logger.info(f"{symbol} Valid Days: {valid_days}")

        # Check first valid index
        first_valid = df[symbol].first_valid_index()
        logger.info(f"First Valid: {first_valid}")

        # Check if it meets 320 days
        if valid_days < 320:
            logger.warning(f"FAIL: {valid_days} < 320")
        else:
            logger.info("PASS: Length check")
    else:
        logger.error(f"{symbol} not in returns matrix")


if __name__ == "__main__":
    check_history()
