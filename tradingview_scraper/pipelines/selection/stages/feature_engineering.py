import logging

import numpy as np
import pandas as pd

from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.utils.predictability import (
    calculate_efficiency_ratio,
    calculate_hurst_exponent,
    calculate_permutation_entropy,
)
from tradingview_scraper.utils.scoring import calculate_liquidity_score

logger = logging.getLogger("pipelines.selection.feature_engineering")


class FeatureEngineeringStage(BasePipelineStage):
    """
    Stage 2: Feature Generation.
    Calculates technical and statistical alpha factors for all assets in the returns matrix.
    """

    @property
    def name(self) -> str:
        return "FeatureEngineering"

    def execute(self, context: SelectionContext) -> SelectionContext:
        df = context.returns_df
        if df.empty:
            logger.warning("FeatureEngineeringStage: Returns matrix is empty. Skipping.")
            return context

        logger.info(f"Generating features for {len(df.columns)} assets...")

        # 1. Base Statistical Features
        mom = df.mean() * 252
        vol = df.std() * np.sqrt(252)
        stability = 1.0 / (vol + 1e-9)

        # 2. Spectral & Complexity Features
        lookback = min(len(df), context.params.get("feature_lookback", 120))

        entropy = pd.Series({s: calculate_permutation_entropy(df[s].tail(lookback).to_numpy(), order=5) for s in df.columns})

        efficiency = pd.Series({s: calculate_efficiency_ratio(df[s].tail(lookback).to_numpy()) for s in df.columns})

        hurst = pd.Series({s: calculate_hurst_exponent(df[s].to_numpy()) for s in df.columns})

        # 3. Discovery Metadata & External Features
        candidate_map = {c["symbol"]: c for c in context.raw_pool}

        adx = pd.Series({s: float(candidate_map.get(s, {}).get("adx") or 0) for s in df.columns})

        # Use v3 standardized liquidity scoring (normalized to $500M)
        liquidity = pd.Series({s: calculate_liquidity_score(str(s), candidate_map) for s in df.columns})

        # Default defaults for Antifragility/Survival (mocking v3 stats_df behavior)
        # In a real pipeline, these would come from an upstream Feature Store or context.external_features
        af_all = pd.Series(0.5, index=df.columns)
        # Apply history scaling (same as v3)
        af_all = af_all * (df.count() / 252.0).clip(upper=1.0)

        regime_all = pd.Series(1.0, index=df.columns)

        # 4. Assemble Feature Store
        features = pd.DataFrame(
            {
                "momentum": mom,
                "stability": stability,
                "entropy": (1.0 - entropy.fillna(1.0)).clip(0, 1),
                "efficiency": efficiency,
                "hurst_clean": (1.0 - (hurst.fillna(0.5) - 0.5).abs() * 2.0).clip(0, 1),
                "adx": adx,
                "liquidity": liquidity,
                "antifragility": af_all,
                "survival": regime_all,
            }
        )

        context.feature_store = features
        context.log_event(self.name, "FeaturesGenerated", {"n_features": len(features.columns), "n_assets": len(features)})

        return context
