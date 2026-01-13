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

        # Vectorized calculation using apply (much faster than dict comprehensions for large N)
        entropy = df.apply(lambda col: calculate_permutation_entropy(col.tail(lookback).to_numpy(), order=5))
        efficiency = df.apply(lambda col: calculate_efficiency_ratio(col.tail(lookback).to_numpy()))
        hurst = df.apply(lambda col: calculate_hurst_exponent(col.to_numpy()))

        # Tail Risk Features (CR-630)
        from scipy.stats import kurtosis, skew

        skewness = df.apply(lambda col: float(skew(col.dropna().to_numpy())) if len(col.dropna()) > 2 else 0.0)
        kurt = df.apply(lambda col: float(kurtosis(col.dropna().to_numpy())) if len(col.dropna()) > 2 else 0.0)
        # CVaR (Expected Shortfall) at 95% confidence
        cvar = df.apply(lambda col: col[col <= col.quantile(0.05)].mean() if len(col.dropna()) > 20 else -0.1)

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
                "entropy": entropy.fillna(1.0).clip(0, 1),  # Raw Permutation Entropy (Noise)
                "efficiency": efficiency,
                "hurst_clean": (1.0 - (hurst.fillna(0.5) - 0.5).abs() * 2.0).clip(0, 1),
                "adx": adx,
                "liquidity": liquidity,
                "antifragility": af_all,
                "survival": regime_all,
                "skew": skewness.fillna(0.0),
                "kurtosis": kurt.fillna(0.0),
                "cvar": cvar.fillna(-0.1),
            }
        )

        context.feature_store = features
        context.log_event(self.name, "FeaturesGenerated", {"n_features": len(features.columns), "n_assets": len(features)})

        return context
