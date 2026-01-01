from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy.stats import rankdata


def calculate_mps_score(metrics: Dict[str, pd.Series], weights: Optional[Dict[str, float]] = None) -> pd.Series:
    """
    Calculates the Multiplicative Probability Score (MPS).
    Score = P1 * P2 * ... * Pn

    If weights are provided, they are used as exponents: P1^w1 * P2^w2 ...
    This allows for 'Importance Weighting' while maintaining multiplicative veto logic.
    """
    if not metrics:
        return pd.Series()

    # Initialize with 1.0
    symbols = list(metrics.values())[0].index
    mps = pd.Series(1.0, index=symbols)

    for name, series in metrics.items():
        # Ensure probability mapping [0, 1]
        p_series = map_to_probability(series)

        if weights and name in weights:
            mps *= p_series ** weights[name]
        else:
            mps *= p_series

    return mps


def map_to_probability(series: pd.Series, method: str = "rank") -> pd.Series:
    """
    Maps raw metrics to a [0, 1] probability space.
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
