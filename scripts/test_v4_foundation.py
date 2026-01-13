import logging

import pandas as pd

from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.stages.feature_engineering import FeatureEngineeringStage
from tradingview_scraper.pipelines.selection.stages.ingestion import IngestionStage

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("v4_foundation_test")


def run_foundation_test():
    logger.info("Starting v4 Selection Pipeline Foundation Test")

    # 1. Initialize Context
    context = SelectionContext(run_id="test_foundation_v4", params={"feature_lookback": 60})

    # 2. Stage 1: Ingestion
    ingestion = IngestionStage()
    try:
        context = ingestion.execute(context)
    except FileNotFoundError as e:
        logger.error(f"Ingestion failed: {e}. Make sure you have artifacts/ data.")
        return

    # 3. Stage 2: Feature Engineering
    if context.returns_df.empty:
        logger.warning("No returns data found. Creating dummy data for test.")
        import numpy as np

        dates = pd.date_range("2023-01-01", periods=100)
        context.returns_df = pd.DataFrame(np.random.normal(0, 0.01, (100, 5)), index=dates, columns=["BTC", "ETH", "SOL", "AAPL", "TSLA"])
        context.raw_pool = [{"symbol": s, "adx": 25, "value_traded": 1e9} for s in context.returns_df.columns]

    feature_eng = FeatureEngineeringStage()
    context = feature_eng.execute(context)

    # 4. Results Audit
    logger.info("Pipeline Foundation Test Results:")
    logger.info(f"Raw Pool Size: {len(context.raw_pool)}")
    logger.info(f"Feature Store Shape: {context.feature_store.shape}")
    logger.info(f"Feature Store Columns: {context.feature_store.columns.tolist()}")

    if not context.feature_store.empty:
        logger.info("\nFeature Snapshot (First 5 assets):")
        print(context.feature_store.head())

    logger.info("\nAudit Trail:")
    for event in context.audit_trail:
        logger.info(f"[{event['stage']}] {event['event']}: {event['data']}")


if __name__ == "__main__":
    run_foundation_test()
