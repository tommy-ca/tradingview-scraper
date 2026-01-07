import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

from tradingview_scraper.portfolio_engines.engines import build_engine
from tradingview_scraper.portfolio_engines.base import EngineRequest
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("clustered_optimizer_v2")

AUDIT_FILE = "data/lakehouse/selection_audit.json"


class ClusteredOptimizerV2:
    def __init__(self, returns_path: str, clusters_path: str, meta_path: str, stats_path: Optional[str] = None):
        self.settings = get_settings()
        self.run_dir = self.settings.prepare_summaries_run_dir()
        self.ledger = None
        if self.settings.features.feat_audit_ledger:
            self.ledger = AuditLedger(self.run_dir)

        # Explicitly cast to DataFrame to satisfy linter
        with open(returns_path, "rb") as f_in:
            df = cast(pd.DataFrame, pd.read_pickle(f_in))
            # Ultra-robust forcing of naive index
            try:
                new_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in df.index]
                df.index = pd.DatetimeIndex(new_idx)
            except Exception as e_idx:
                logger.warning(f"Fallback indexing for returns: {e_idx}")
                df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
            self.returns = df

        with open(clusters_path, "r") as f:
            self.clusters = cast(Dict[str, List[str]], json.load(f))
        with open(meta_path, "r") as f:
            self.meta = cast(Dict[str, Any], json.load(f))
        self.stats = None
        if stats_path and os.path.exists(stats_path):
            with open(stats_path, "r") as f:
                self.stats = cast(pd.DataFrame, pd.read_json(f))

    def run_profile(self, profile: str, engine_name: str = "custom", cluster_cap: float = 0.25) -> pd.DataFrame:
        """Entry point for standard risk profiles using the engine factory."""
        if self.ledger:
            self.ledger.record_intent(step=f"optimize_{profile}", params={"engine": engine_name, "cap": cluster_cap}, input_hashes={"returns": get_df_hash(self.returns)})

        try:
            engine = build_engine(engine_name)
            request = EngineRequest(profile=profile, cluster_cap=cluster_cap)
            response = engine.optimize(returns=self.returns, clusters=self.clusters, meta=self.meta, stats=self.stats, request=request)
            weights_df = response.weights
        except Exception as e:
            logger.error(f"Optimization failed for {profile}: {e}")
            return pd.DataFrame()

        if self.ledger:
            self.ledger.record_outcome(step=f"optimize_{profile}", status="success", output_hashes={"weights": get_df_hash(weights_df)}, metrics={"n_assets": len(weights_df)})
        return weights_df

    def run_barbell(self, cluster_cap: float = 0.25, regime: str = "NORMAL") -> pd.DataFrame:
        """Entry point for the Antifragile Barbell profile using the custom engine."""
        return self.run_profile("barbell", "custom", cluster_cap)


if __name__ == "__main__":
    from tradingview_scraper.regime import MarketRegimeDetector

    optimizer = ClusteredOptimizerV2(
        returns_path="data/lakehouse/portfolio_returns.pkl",
        clusters_path="data/lakehouse/portfolio_clusters.json",
        meta_path="data/lakehouse/portfolio_meta.json",
        stats_path="data/lakehouse/antifragility_stats.json",
    )

    detector = MarketRegimeDetector()
    regime, score = detector.detect_regime(optimizer.returns)
    logger.info(f"Regime Detected for Optimization: {regime} (Score: {score:.2f})")

    cap = float(os.getenv("CLUSTER_CAP", "0.25"))

    # Generate results for each profile
    profiles = {}
    for p_name, method in [
        ("min_variance", "min_variance"),
        ("hrp", "hrp"),
        ("max_sharpe", "max_sharpe"),
        ("equal_weight", "equal_weight"),
    ]:
        logger.info(f"Optimizing profile: {p_name}")
        weights_df = optimizer.run_profile(method, "custom", cap)

        if weights_df.empty:
            logger.warning(f"Optimization returned empty weights for {p_name}")
            profiles[p_name] = {"assets": [], "clusters": []}
            continue
        cluster_summary = []
        for c_id in optimizer.clusters.keys():
            sub = weights_df[weights_df["Cluster_ID"] == str(c_id)]
            if sub.empty:
                continue
            gross = sub["Weight"].sum()
            net = sub["Net_Weight"].sum()
            cluster_summary.append(
                {
                    "Cluster_Label": f"Cluster {c_id}",
                    "Gross_Weight": float(gross),
                    "Net_Weight": float(net),
                    "Lead_Asset": sub.iloc[0]["Symbol"],
                    "Asset_Count": len(sub),
                    "Type": "CORE",  # Placeholder
                    "Sectors": list(sub["Sector"].unique()),
                }
            )

        profiles[p_name] = {
            "assets": weights_df.to_dict(orient="records"),
            "clusters": cluster_summary,
        }

    # Add Antifragile Barbell
    logger.info("Optimizing profile: barbell")
    barbell_df = optimizer.run_barbell(cap, regime)
    if not barbell_df.empty:
        barbell_summary = []
        for c_id in optimizer.clusters.keys():
            sub = barbell_df[barbell_df["Cluster_ID"] == str(c_id)]
            if sub.empty:
                continue
            gross = sub["Weight"].sum()
            net = sub["Net_Weight"].sum()
            barbell_summary.append(
                {
                    "Cluster_Label": f"Cluster {c_id}",
                    "Gross_Weight": float(gross),
                    "Net_Weight": float(net),
                    "Lead_Asset": sub.iloc[0]["Symbol"],
                    "Asset_Count": len(sub),
                    "Type": sub.iloc[0]["Type"],
                    "Sectors": list(sub["Sector"].unique()),
                }
            )
        profiles["barbell"] = {
            "assets": barbell_df.to_dict(orient="records"),
            "clusters": barbell_summary,
        }
    else:
        reason = "missing antifragility stats" if optimizer.stats is None else "barbell unavailable"
        profiles["barbell"] = {
            "assets": [],
            "clusters": [],
            "meta": {"skipped": True, "reason": reason},
        }

    # Build cluster registry
    registry = {}
    for c_id, symbols in optimizer.clusters.items():
        # Find primary sector from meta
        sectors = [optimizer.meta.get(s, {}).get("sector", "N/A") for s in symbols]
        primary = max(set(sectors), key=sectors.count) if sectors else "N/A"
        registry[c_id] = {"symbols": symbols, "primary_sector": primary}

    output = {
        "profiles": profiles,
        "cluster_registry": registry,
        "optimization": {"regime": {"name": regime, "score": float(score)}},
        "metadata": {"generated_at": datetime.now().isoformat(), "cluster_cap": cap},
    }

    output_path = "data/lakehouse/portfolio_optimized_v2.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"✅ Clustered Optimization V2 Complete. Saved to: {output_path}")
