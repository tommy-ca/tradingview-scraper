import logging

import numpy as np
import pandas as pd

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.utils.predictability import (
    calculate_efficiency_ratio,
    calculate_hurst_exponent,
    calculate_permutation_entropy,
)
from tradingview_scraper.utils.scoring import calculate_liquidity_score_vectorized

logger = logging.getLogger("pipelines.selection.feature_engineering")


@StageRegistry.register(id="foundation.features", name="Feature Engineering", description="Calculates technical alpha factors", category="foundation")
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

        skewness = df.apply(lambda col: float(abs(skew(col.dropna().to_numpy()))) if len(col.dropna()) > 2 else 0.0)
        kurt = df.apply(lambda col: float(kurtosis(col.dropna().to_numpy())) if len(col.dropna()) > 2 else 0.0)
        # CVaR (Expected Shortfall) at 95% confidence
        cvar = df.apply(lambda col: col[col <= col.quantile(0.05)].mean() if len(col.dropna()) > 20 else -0.1)

        # 3. Discovery Metadata & External Features
        pool_df = pd.DataFrame(context.raw_pool)
        if not pool_df.empty:
            pool_df = pool_df.set_index("symbol")
            pool_df = pool_df.reindex(df.columns)
        else:
            pool_df = pd.DataFrame(index=df.columns)

        def get_col(col_name, default=0.0):
            if col_name in pool_df.columns:
                return pd.to_numeric(pool_df[col_name], errors="coerce").fillna(default)
            return pd.Series(default, index=df.columns)

        adx = get_col("adx")
        rec_all = get_col("recommend_all")
        rec_ma = get_col("recommend_ma")
        rec_other = get_col("recommend_other")
        roc = get_col("roc")
        vol_d = get_col("volatility_d")
        vol_chg = get_col("volume_change_pct")

        # Vectorized liquidity
        liquidity = calculate_liquidity_score_vectorized(pool_df)

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
                "entropy": pd.to_numeric(entropy, errors="coerce").fillna(1.0).clip(0, 1),  # Raw Permutation Entropy (Noise)
                "efficiency": pd.to_numeric(efficiency, errors="coerce"),
                "hurst_clean": (1.0 - (pd.to_numeric(hurst, errors="coerce").fillna(0.5) - 0.5).abs() * 2.0).clip(0, 1),
                "adx": adx,
                "recommend_all": rec_all,
                "recommend_ma": rec_ma,
                "recommend_other": rec_other,
                "roc": roc,
                "volatility_d": vol_d,
                "volume_change_pct": vol_chg,
                "liquidity": liquidity,
                "antifragility": af_all,
                "survival": regime_all,
                "skew": skewness.fillna(0.0),
                "kurtosis": kurt.fillna(0.0),
                "cvar": cvar.fillna(-0.1),
            }
        ).astype(float)  # Force global numeric consistency (CR-FIX Phase 353)

        context.feature_store = features
        context.log_event(self.name, "FeaturesGenerated", {"n_features": len(features.columns), "n_assets": len(features)})

        return context
