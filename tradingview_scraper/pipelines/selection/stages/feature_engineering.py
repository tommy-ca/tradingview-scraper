import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, skew

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.utils.predictability import (
    calculate_efficiency_ratio,
    calculate_hurst_exponent,
    calculate_permutation_entropy,
)
from tradingview_scraper.utils.scoring import calculate_liquidity_score

logger = logging.getLogger("pipelines.selection.feature_engineering")


@StageRegistry.register(id="foundation.features", name="Feature Engineering", description="Calculates technical alpha factors", category="foundation")
class FeatureEngineeringStage(BasePipelineStage):
    """
    Stage 2: Feature Generation.
    Calculates technical and statistical alpha factors for all assets in the returns matrix.
    """

    # Constants
    ANNUALIZATION_FACTOR = 252
    VOL_FACTOR = np.sqrt(252)
    EPSILON = 1e-9
    DEFAULT_LOOKBACK = 120
    CVAR_CONFIDENCE = 0.05
    CVAR_MIN_OBSERVATIONS = 20

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
        base_features = self._calculate_base_features(df)

        # 2. Spectral & Complexity Features
        lookback = min(len(df), context.params.get("feature_lookback", self.DEFAULT_LOOKBACK))
        spectral_features = self._calculate_spectral_features(df, lookback)

        # 3. Tail Risk Features
        tail_features = self._calculate_tail_features(df)

        # 4. Discovery Metadata & External Features
        metadata_features = self._extract_metadata_features(df, context.raw_pool)

        # 5. Assemble Feature Store
        features = pd.concat([base_features, spectral_features, tail_features, metadata_features], axis=1)

        # Force global numeric consistency (CR-FIX Phase 353)
        features = features.astype(float)

        context.feature_store = features
        context.log_event(self.name, "FeaturesGenerated", {"n_features": len(features.columns), "n_assets": len(features)})

        return context

    def _calculate_base_features(self, df: pd.DataFrame) -> pd.DataFrame:
        mom = df.mean() * self.ANNUALIZATION_FACTOR
        vol = df.std() * self.VOL_FACTOR
        stability = 1.0 / (vol + self.EPSILON)

        return pd.DataFrame({"momentum": mom, "stability": stability})

    def _calculate_spectral_features(self, df: pd.DataFrame, lookback: int) -> pd.DataFrame:
        # Vectorized calculation using apply (much faster than dict comprehensions for large N)
        entropy = df.apply(lambda col: calculate_permutation_entropy(col.tail(lookback).to_numpy(), order=5))
        efficiency = df.apply(lambda col: calculate_efficiency_ratio(col.tail(lookback).to_numpy()))
        hurst = df.apply(lambda col: calculate_hurst_exponent(col.to_numpy()))

        # Process raw values
        entropy_clean = pd.to_numeric(entropy, errors="coerce").fillna(1.0).clip(0, 1)  # Raw Permutation Entropy (Noise)
        efficiency_clean = pd.to_numeric(efficiency, errors="coerce")

        # Hurst transformation: (1.0 - abs(hurst - 0.5) * 2.0)
        hurst_val = pd.to_numeric(hurst, errors="coerce").fillna(0.5)
        hurst_clean = (1.0 - (hurst_val - 0.5).abs() * 2.0).clip(0, 1)

        return pd.DataFrame({"entropy": entropy_clean, "efficiency": efficiency_clean, "hurst_clean": hurst_clean})

    def _calculate_tail_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Use scipy.stats vectorized operations where possible

        # Skewness (Absolute)
        skew_vals = skew(df, axis=0, nan_policy="omit")
        skewness = pd.Series(skew_vals, index=df.columns).abs()

        # Kurtosis
        kurt_vals = kurtosis(df, axis=0, nan_policy="omit")
        kurt = pd.Series(kurt_vals, index=df.columns)

        # CVaR (Expected Shortfall) at 95% confidence
        def calculate_cvar(col):
            valid = col.dropna()
            if len(valid) <= self.CVAR_MIN_OBSERVATIONS:
                return -0.1
            cutoff = valid.quantile(self.CVAR_CONFIDENCE)
            if pd.isna(cutoff):
                return -0.1
            loss_tail = valid[valid <= cutoff]
            if loss_tail.empty:
                return -0.1
            return loss_tail.mean()

        cvar = df.apply(calculate_cvar)

        return pd.DataFrame({"skew": skewness.fillna(0.0), "kurtosis": kurt.fillna(0.0), "cvar": cvar.fillna(-0.1)})

    def _extract_metadata_features(self, df: pd.DataFrame, raw_pool: List[Dict[str, Any]]) -> pd.DataFrame:
        # Optimization: Create a DataFrame from raw_pool and reindex
        if raw_pool:
            pool_df = pd.DataFrame(raw_pool)
            if "symbol" in pool_df.columns:
                pool_df = pool_df.set_index("symbol")
                pool_df = pool_df[~pool_df.index.duplicated(keep="first")]
            else:
                pool_df = pd.DataFrame()
        else:
            pool_df = pd.DataFrame()

        aligned_pool = pool_df.reindex(df.columns)

        def get_series(col_name: str, fill_value: float = 0.0) -> pd.Series:
            if col_name in aligned_pool.columns:
                return pd.to_numeric(aligned_pool[col_name], errors="coerce").fillna(fill_value)
            return pd.Series(fill_value, index=df.columns)

        adx = get_series("adx")
        rec_all = get_series("recommend_all")
        rec_ma = get_series("recommend_ma")
        rec_other = get_series("recommend_other")
        roc = get_series("roc")
        vol_d = get_series("volatility_d")
        vol_chg = get_series("volume_change_pct")

        # Liquidity scoring
        candidate_map = {c["symbol"]: c for c in raw_pool}
        liquidity = pd.Series({s: calculate_liquidity_score(str(s), candidate_map) for s in df.columns})

        # Antifragility & Survival
        # Apply history scaling (same as v3)
        af_all = pd.Series(0.5, index=df.columns)
        af_all = af_all * (df.count() / self.ANNUALIZATION_FACTOR).clip(upper=1.0)

        regime_all = pd.Series(1.0, index=df.columns)

        return pd.DataFrame(
            {
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
            }
        )
