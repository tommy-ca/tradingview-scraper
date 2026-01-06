import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, cast

import pandas as pd

from tradingview_scraper.portfolio_engines.base import EngineRequest
from tradingview_scraper.portfolio_engines.engines import build_engine
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("generate_orders_v3")


def generate_production_orders():
    settings = get_settings()

    # 1. Load Data
    returns_path = "data/lakehouse/portfolio_returns.pkl"
    clusters_path = "data/lakehouse/portfolio_clusters.json"
    meta_path = "data/lakehouse/portfolio_meta.json"
    stats_path = "data/lakehouse/antifragility_stats.json"

    with open(returns_path, "rb") as f:
        returns = cast(pd.DataFrame, pd.read_pickle(f))
    with open(clusters_path, "r") as f:
        clusters = cast(Dict[str, List[str]], json.load(f))
    with open(meta_path, "r") as f:
        meta = cast(Dict[str, Any], json.load(f))

    stats = None
    if os.path.exists(stats_path):
        stats = pd.read_json(stats_path)

    # 2. Detect Regime
    detector = MarketRegimeDetector()
    regime, score = detector.detect_regime(returns)
    logger.info(f"Current Market Regime: {regime} (Score: {score:.2f})")

    # 3. Instantiate Winner Engine (Riskfolio)
    engine = build_engine("riskfolio")

    # 4. Generate Orders for the Winning Profile (Barbell)
    request = EngineRequest(
        profile="barbell",
        cluster_cap=0.25,
        regime=regime,
        market_environment=regime,  # Simplification for unified engines
    )

    logger.info("Generating orders for winner: riskfolio/barbell")
    response = engine.optimize(returns=returns, clusters=clusters, meta=meta, stats=stats, request=request)

    weights_df = response.weights
    if weights_df.empty:
        logger.error("Optimization failed to produce weights.")
        return

    # 5. Add Provenance Metadata
    weights_df["Regime"] = regime
    weights_df["Regime_Score"] = score
    weights_df["Generated_At"] = datetime.now().isoformat()
    weights_df["Engine"] = "riskfolio"
    weights_df["Profile"] = "barbell"

    # 6. Format Action column (Target Weights for now)
    # Note: track_portfolio_state.py handles Drift vs Actual holdings.
    # This script produces the 'Ideal' target state.

    output_dir = "data/lakehouse/orders"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"target_weights_{datetime.now().strftime('%Y%m%d')}.csv")

    weights_df.to_csv(output_path, index=False)
    logger.info(f"✅ Production Orders (V3) Generated: {output_path}")

    # Also update the global pointer
    latest_path = "data/lakehouse/portfolio_optimized_v3.json"

    # Structure for JSON persistence
    output_json = {
        "profile": "barbell",
        "engine": "riskfolio",
        "regime": {"name": regime, "score": float(score)},
        "assets": weights_df.to_dict(orient="records"),
        "metadata": {"generated_at": datetime.now().isoformat(), "source_returns_hash": "TODO", "cluster_cap": 0.25},
    }

    with open(latest_path, "w") as f:
        json.dump(output_json, f, indent=2)
    logger.info(f"✅ Optimized State (V3) Persisted: {latest_path}")


if __name__ == "__main__":
    generate_production_orders()
