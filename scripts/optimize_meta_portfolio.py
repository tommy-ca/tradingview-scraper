import argparse
import json
import logging
import os
import sys

import pandas as pd

sys.path.append(os.getcwd())
from tradingview_scraper.portfolio_engines.base import EngineRequest, ProfileName
from tradingview_scraper.portfolio_engines.engines import build_engine
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("optimize_meta_portfolio")


def optimize_meta(returns_path: str, output_path: str):
    settings = get_settings()
    run_dir = settings.prepare_summaries_run_dir()
    ledger = AuditLedger(run_dir) if settings.features.feat_audit_ledger else None

    if not os.path.exists(returns_path):
        logger.error(f"Meta-Returns missing: {returns_path}")
        return

    meta_rets = pd.read_pickle(returns_path)
    if meta_rets.empty:
        logger.error("Meta-Returns is empty.")
        return

    logger.info(f"Optimizing meta-portfolio over {len(meta_rets.columns)} sleeves.")

    # 1. Define meta-clusters: each sleeve is a cluster of 1
    clusters = {str(col): [str(col)] for col in meta_rets.columns}

    # 2. Audit Intent
    if ledger:
        ledger.record_intent(
            step="meta_optimize",
            params={"engine": "custom", "profile": "hrp", "n_sleeves": len(meta_rets.columns)},
            input_hashes={"meta_returns": get_df_hash(meta_rets)},
            context={"meta_profile": "meta_production"},
        )

    # 3. Use the Custom engine to run HRP
    engine = build_engine("custom")

    request = EngineRequest(profile=cast(ProfileName, "hrp"), engine="custom", cluster_cap=1.0)

    try:
        response = engine.optimize(returns=meta_rets, clusters=clusters, meta={}, stats=pd.DataFrame(), request=request)

        weights_df = response.weights
        if weights_df.empty:
            logger.error("Optimization produced empty weights.")
            return

        logger.info("\n--- Meta-Allocation Weights ---")
        print(weights_df[["Symbol", "Weight"]].to_string(index=False))

        # 4. Audit Outcome
        if ledger:
            ledger.record_outcome(
                step="meta_optimize",
                status="success",
                output_hashes={"meta_weights": get_df_hash(weights_df)},
                metrics={"n_sleeves": len(weights_df)},
                data={"weights": weights_df.set_index("Symbol")["Weight"].to_dict()},
                context={"meta_profile": "meta_production"},
            )

        # 5. Save Artifact
        artifact = {
            "metadata": {"source": returns_path, "engine": "custom", "profile": "hrp", "n_sleeves": len(meta_rets.columns), "run_id": settings.run_id},
            "weights": weights_df.to_dict(orient="records"),
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(artifact, f, indent=2)

        logger.info(f"\nSaved meta-optimized weights to {output_path}")

    except Exception as e:
        logger.error(f"Meta-optimization failed: {e}")
        if ledger:
            ledger.record_outcome(step="meta_optimize", status="error", output_hashes={"error": "none"}, metrics={"error": str(e)}, context={"meta_profile": "meta_production"})
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    from typing import cast

    parser = argparse.ArgumentParser()
    parser.add_argument("--returns", default="data/lakehouse/meta_returns.pkl")
    parser.add_argument("--output", default="data/lakehouse/meta_optimized.json")
    args = parser.parse_args()

    optimize_meta(args.returns, args.output)
