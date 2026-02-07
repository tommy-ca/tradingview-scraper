from __future__ import annotations

import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tradingview_scraper.settings import TradingViewScraperSettings


def apply_diversity_constraints(flat_weights: pd.DataFrame, settings: TradingViewScraperSettings) -> None:
    """
    Standardizes weight clipping and normalization based on cluster_cap.
    (Pillar 3: Diversity Compliance).
    """
    cluster_cap = settings.cluster_cap
    w_sum_abs = flat_weights["Weight"].sum()

    if w_sum_abs > 0:
        # 1. Clip individual weights based on the configurable cap
        flat_weights["Weight"] = flat_weights["Weight"].clip(upper=cluster_cap * w_sum_abs)
        flat_weights["Net_Weight"] = flat_weights["Net_Weight"].clip(lower=-cluster_cap * w_sum_abs, upper=cluster_cap * w_sum_abs)

        # 2. Re-normalize to preserve original absolute exposure
        new_sum = flat_weights["Weight"].sum()
        if new_sum > 0:
            scale = w_sum_abs / new_sum
            flat_weights["Weight"] *= scale
            flat_weights["Net_Weight"] *= scale
