import json
import logging
import os
import sys

import numpy as np
import pandas as pd

from tradingview_scraper.pipelines.selection.pipeline import SelectionPipeline

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("v4_pipeline_test")


def run_pipeline_test():
    logger.info("Starting v4 Selection Pipeline Integration Test")

    # Generate Dummy Data if missing
    dummy_cands = "data/lakehouse/test_pipeline_candidates.json"
    dummy_rets = "data/lakehouse/test_pipeline_returns.csv"

    if not os.path.exists(dummy_rets):
        logger.info("Generating dummy data for test...")
        # 50 assets
        syms = [f"ASSET_{i}" for i in range(50)]
        # Candidates
        cands = [{"symbol": s, "adx": 30.0, "value_traded": 1e9, "direction": "LONG"} for s in syms]
        with open(dummy_cands, "w") as f:
            json.dump(cands, f)

        # Returns
        dates = pd.date_range("2023-01-01", periods=200)
        rets = pd.DataFrame(np.random.normal(0, 0.02, (200, 50)), index=dates, columns=syms)
        # Add a clear winner (High Momentum)
        rets["ASSET_0"] += 0.005
        rets.to_csv(dummy_rets)

    try:
        pipeline = SelectionPipeline(run_id="test_v4_integration", candidates_path=dummy_cands, returns_path=dummy_rets)
        context = pipeline.run()

        logger.info("\n--- Pipeline Result Summary ---")
        logger.info(f"Final Winners: {len(context.winners)}")
        logger.info(f"Strategy Atoms: {len(context.strategy_atoms)}")
        logger.info(f"Composition Map Keys: {len(context.composition_map)}")

        if context.winners:
            logger.info(f"Sample Winner: {context.winners[0]['symbol']} (Score: {context.winners[0].get('alpha_score', 'N/A')})")

        logger.info("\n--- Audit Trail (Stages) ---")
        seen_stages = set()
        for event in context.audit_trail:
            if event["stage"] not in seen_stages:
                logger.info(f"Executed: {event['stage']}")
                seen_stages.add(event["stage"])

        logger.info("✅ Test Passed: Pipeline executed successfully.")

    except Exception as e:
        logger.error(f"❌ Test Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline_test()
