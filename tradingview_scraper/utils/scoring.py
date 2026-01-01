from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def rank_series(series: pd.Series) -> pd.Series:
    """Robust ranking: handles NaNs and identical values."""
    if series.empty:
        return series
    ranks = rankdata(series.fillna(series.min()))
    return pd.Series(ranks / len(ranks), index=series.index)


def normalize_series(series: pd.Series) -> pd.Series:
    """Standard [0, 1] normalization."""
    if series.empty or series.max() == series.min():
        return pd.Series(0.5, index=series.index)
    return (series - series.min()) / (series.max() - series.min())


def calculate_liquidity_score(symbol: str, candidate_map: Dict[str, Any]) -> float:
    """Extracts a normalized liquidity score from candidate metadata."""
    meta = candidate_map.get(symbol, {})
    vt = float(meta.get("value_traded") or meta.get("Value.Traded") or 0)
    # Institutional baseline: $500M ADV = 1.0
    return min(1.0, vt / 5e8)


def calculate_mps_score(metrics: Dict[str, pd.Series], weights: Optional[Dict[str, float]] = None, methods: Optional[Dict[str, str]] = None) -> pd.Series:
    """
    Calculates the Multiplicative Probability Score (MPS).
    Score = P1 * P2 * ... * Pn

    If weights are provided, they are used as exponents: P1^w1 * P2^w2 ...
    If methods are provided, they define how to map the raw metric to [0, 1].
    """
    if not metrics:
        return pd.Series()

    # Initialize with 1.0
    symbols = list(metrics.values())[0].index
    mps = pd.Series(1.0, index=symbols)

    for name, series in metrics.items():
        # Determine mapping method (default to rank)
        method = (methods or {}).get(name, "rank")

        # Ensure probability mapping [0, 1]
        p_series = map_to_probability(series, method=method)

        if weights and name in weights:
            mps *= p_series ** weights[name]
        else:
            mps *= p_series

    return mps


def map_to_probability(series: pd.Series, method: str = "rank") -> pd.Series:
    """
    Maps raw metrics to a [0, 1] probability space.
    - rank: [0.01, 1.0] relative percentile.
    - logistic: S-curve based on Z-score.
    - cdf: Cumulative Distribution Function (Normal).
    """
    if series.empty:
        return series

    if method == "rank":
        # Percentile rank [0.01, 1.0] - Avoid absolute zero to prevent total collapse from noise
        ranks = rankdata(series.fillna(series.min()))
        return pd.Series(0.01 + (0.99 * (ranks - 1) / (len(ranks) - 1 if len(ranks) > 1 else 1)), index=series.index)

    elif method == "logistic":
        # S-curve mapping
        mu = series.mean()
        sigma = series.std() + 1e-9
        return 1 / (1 + np.exp(-(series - mu) / sigma))

    elif method == "cdf":
        # Raw value mapping if already in [0, 1] - DO NOT normalize to maintain absolute probability space
        if series.min() >= 0 and series.max() <= 1:
            return series.clip(0.001, 1.0)

        from scipy.stats import norm

        mu = series.mean()
        sigma = series.std() + 1e-9
        z = (series - mu) / sigma
        return pd.Series(norm.cdf(z).clip(0.001, 1.0), index=series.index)

    return series


def calculate_survival_probability(bars: pd.Series, gap_pct: pd.Series, regime_score: pd.Series) -> pd.Series:
    """
    Combines health metrics into a single Survival Probability P(Survival).
    """
    # 1. History Probability (Log-Logistic)
    # 252 bars is 0.5 probability
    p_history = 1 / (1 + (252 / (bars + 1e-9)) ** 2)

    # 2. Gap Penalty
    p_gaps = (1.0 - gap_pct).clip(0, 1)

    # 3. Regime Survival
    p_regime = regime_score.clip(0.01, 1.0)

    return p_history * p_gaps * p_regime
