import logging
from typing import Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FeatureConsistencyValidator:
    """
    Validates the Point-in-Time (PIT) integrity of the feature store.
    """

    # Feature Bounds Configuration
    BOUNDS = {
        "recommend_all": (-1.0, 1.0),
        "recommend_ma": (-1.0, 1.0),
        "recommend_other": (-1.0, 1.0),
        "adx": (0.0, 100.0),
        "rsi": (0.0, 100.0),
        "volatility_d": (0.0, float("inf")),
        "sma_50": (0.0, float("inf")),
        "sma_200": (0.0, float("inf")),
        "vwma_20": (0.0, float("inf")),
        "adx_14": (0.0, 100.0),
        "dmp_14": (0.0, 100.0),
        "dmn_14": (0.0, 100.0),
        "donchian_lower_20": (0.0, float("inf")),
        "donchian_upper_20": (0.0, float("inf")),
        "bb_width_20": (0.0, float("inf")),
    }

    @staticmethod
    def audit_coverage(features_df: pd.DataFrame, returns_df: pd.DataFrame) -> list[str]:
        """
        Ensures that all symbols in returns have corresponding features.
        Returns a list of missing symbols.
        """
        if features_df.empty or returns_df.empty:
            return []

        # Handle MultiIndex columns in features (symbol, feature)
        if isinstance(features_df.columns, pd.MultiIndex):
            feature_symbols = set(features_df.columns.get_level_values(0).unique())
        else:
            feature_symbols = set(features_df.columns)

        return_symbols = set(returns_df.columns)

        missing = sorted(list(return_symbols - feature_symbols))
        if missing:
            logger.warning(f"Feature Store Audit: {len(missing)} symbols missing from feature matrix: {missing[:5]}...")

        return missing

    @staticmethod
    def check_nan_density(series: pd.Series, max_pct: float = 0.10) -> bool:
        """
        Returns True if the series is 'Degraded' (NaN density > max_pct).
        Ignores leading NaNs (warm-up).
        """
        first_valid = series.first_valid_index()
        if first_valid is None:
            return True

        production_history = series.loc[first_valid:]
        nan_pct = production_history.isna().mean()

        return bool(nan_pct > max_pct)

    @staticmethod
    def check_lag(series: pd.Series, max_lag_days: int = 3) -> bool:
        """
        Returns True if the series has stopped updating (Lagging).
        Checks if the last valid index is older than `max_lag_days` from the series end.
        """
        if series.dropna().empty:
            return True

        last_valid = series.last_valid_index()
        last_index = series.index[-1]

        # Ensure timestamps
        if not isinstance(last_valid, pd.Timestamp) or not isinstance(last_index, pd.Timestamp):
            return False  # Cannot determine lag without timestamps

        lag = (last_index - last_valid).days
        return lag > max_lag_days

    @staticmethod
    def check_bounds(series: pd.Series, min_val: float, max_val: float) -> bool:
        """
        Returns True if all values are within [min_val, max_val].
        Ignores NaNs.
        """
        # Optimized check: min/max of the series
        # Drop NaNs first
        s = series.dropna()
        if s.empty:
            return True

        s_min = s.min()
        s_max = s.max()

        return s_min >= min_val and s_max <= max_val

    @classmethod
    def validate_history(cls, df: pd.DataFrame, strict: bool = False) -> dict[str, list[str]]:
        """
        Validates the full historical matrix.
        Returns dictionary of failures: {'missing': [...], 'degraded': [...], 'lagging': [...], 'out_of_bounds': [...]}
        """
        report = {"degraded": [], "lagging": [], "out_of_bounds": []}

        if df.empty:
            return report

        # Expect MultiIndex (symbol, feature)
        if not isinstance(df.columns, pd.MultiIndex):
            logger.warning("Feature matrix does not have MultiIndex columns. Skipping deep validation.")
            return report

        symbols = df.columns.get_level_values(0).unique()

        for sym in symbols:
            # Check degradation on a representative feature (e.g. recommend_all or first available)
            # We usually check 'recommend_all' or 'adx' for liveness
            features = df[sym].columns

            # 1. Density Check (on 'recommend_all' if present, else aggregate?)
            # Let's check 'recommend_all' as the heartbeat
            if "recommend_all" in features:
                s_rec = df[(sym, "recommend_all")]
                if isinstance(s_rec, pd.DataFrame):  # Defensive check for duplicate columns
                    s_rec = s_rec.iloc[:, 0]

                if cls.check_nan_density(s_rec):
                    report["degraded"].append(sym)
                if cls.check_lag(s_rec):
                    report["lagging"].append(sym)
                if not cls.check_bounds(s_rec, *cls.BOUNDS["recommend_all"]):
                    if sym not in report["out_of_bounds"]:
                        report["out_of_bounds"].append(sym)

            # 2. Bounds Check (on all known features)
            for feat in features:
                if feat in cls.BOUNDS:
                    s_feat = df[(sym, feat)]
                    if isinstance(s_feat, pd.DataFrame):
                        s_feat = s_feat.iloc[:, 0]

                    min_v, max_v = cls.BOUNDS[feat]
                    if not cls.check_bounds(s_feat, min_v, max_v):
                        if sym not in report["out_of_bounds"]:
                            report["out_of_bounds"].append(sym)

        return report
