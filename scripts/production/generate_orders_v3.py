import argparse
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
from tradingview_scraper.utils.audit import get_df_hash

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("generate_orders_v3")


def generate_production_orders(source_run_id: str = "20260106-prod-q1"):
    settings = get_settings()

    # 1. Load Tournament Results to find the Winner
    candidates_path = f"artifacts/summaries/runs/{source_run_id}/data/tournament_candidates.csv"
    if not os.path.exists(candidates_path):
        logger.error(f"Source run candidates not found: {candidates_path}")
        return

    candidates_df = pd.read_csv(candidates_path)
    if candidates_df.empty:
        logger.error(f"Source run has no candidates: {source_run_id}")
        return

    # Select the #1 Candidate (Top row)
    winner = candidates_df.iloc[0]
    selection_mode = str(winner.get("selection", "v3.2"))
    engine_name = str(winner.get("engine", "riskfolio"))
    profile_name = str(winner.get("profile", "barbell"))

    logger.info(f"🏆 Top Candidate from {source_run_id}: {engine_name}/{profile_name} (Mode: {selection_mode})")

    # 2. Load Live Data
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

    # 3. Detect Regime
    detector = MarketRegimeDetector()
    regime, score = detector.detect_regime(returns)
    logger.info(f"Current Market Regime: {regime} (Score: {score:.2f})")

    # 4. Instantiate Winner Engine
    engine = build_engine(engine_name)

    # 5. Generate Orders for the Winning Profile
    request = EngineRequest(
        profile=cast(Any, profile_name),
        cluster_cap=0.25,
        regime=regime,
        market_environment=regime,  # Simplification for unified engines
    )

    logger.info(f"Generating orders for: {engine_name}/{profile_name}")
    response = engine.optimize(returns=returns, clusters=clusters, meta=meta, stats=stats, request=request)

    weights_df = response.weights
    if weights_df.empty:
        logger.error("Optimization failed to produce weights.")
        return

    # 6. Add Provenance Metadata
    weights_df["Regime"] = regime
    weights_df["Regime_Score"] = score
    weights_df["Generated_At"] = datetime.now().isoformat()
    weights_df["Engine"] = engine_name
    weights_df["Profile"] = profile_name
    weights_df["Source_Run"] = source_run_id

    # 7. Persist Artifacts
    output_dir = "data/lakehouse/orders"
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d")
    output_path = os.path.join(output_dir, f"target_weights_{ts}.csv")

    weights_df.to_csv(output_path, index=False)
    logger.info(f"✅ Production Orders (V3) Generated: {output_path}")

    # Also update the global pointer
    latest_path = "data/lakehouse/portfolio_optimized_v3.json"

    # Structure for JSON persistence
    output_json = {
        "profile": profile_name,
        "engine": engine_name,
        "regime": {"name": regime, "score": float(score)},
        "assets": weights_df.to_dict(orient="records"),
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source_run_id": source_run_id,
            "selection_mode": selection_mode,
            "source_returns_hash": get_df_hash(returns),
            "cluster_cap": 0.25,
        },
    }

    with open(latest_path, "w") as f:
        json.dump(output_json, f, indent=2)
    logger.info(f"✅ Optimized State (V3) Persisted: {latest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auditable production order generator")
    parser.add_argument("--source-run-id", type=str, default="20260106-prod-q1", help="Run ID to pull the winner from")
    args = parser.parse_args()

    generate_production_orders(source_run_id=args.source_run_id)
