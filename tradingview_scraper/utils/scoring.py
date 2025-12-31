from typing import Any, Dict

import numpy as np
import pandas as pd


def calculate_liquidity_score(symbol: str, meta: Dict[str, Any], alpha: float = 0.7, beta: float = 0.3) -> float:
    """
    Calculates a consistent Liquidity Score based on Value Traded and Spread Proxy.

    Score = alpha * log1p(ValueTraded) + beta * log1p(1 / SpreadPct)
    """
    m = meta.get(symbol, {})
    vt = float(m.get("value_traded", 0) or 0)
    atr = float(m.get("atr", 0) or 0)
    price = float(m.get("close", 0) or 0)

    spread_proxy = 0.0
    if atr > 0 and price > 0:
        spread_pct = atr / price
        spread_pct = max(spread_pct, 1e-6)
        spread_proxy = 1.0 / spread_pct
        spread_proxy = min(spread_proxy, 1e6)

    # Weighted Liquidity
    return alpha * np.log1p(max(vt, 0.0)) + beta * np.log1p(spread_proxy)


def rank_series(s: pd.Series) -> pd.Series:
    """Percentile ranking for robust cross-sectional comparison."""
    if len(s) <= 1:
        return pd.Series(0.5, index=s.index)
    return s.rank(pct=True)


def normalize_series(s: pd.Series) -> pd.Series:
    """Min-max normalization with epsilon guard."""
    if len(s) <= 1:
        return pd.Series(1.0, index=s.index)

    s_min = s.min()
    s_max = s.max()
    diff = s_max - s_min
    if diff < 1e-9:
        return pd.Series(1.0, index=s.index)

    return (s - s_min) / diff
