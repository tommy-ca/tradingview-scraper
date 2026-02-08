from __future__ import annotations

import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tradingview_scraper.settings import TradingViewScraperSettings


def apply_diversity_constraints(flat_weights: pd.DataFrame, settings: TradingViewScraperSettings) -> None:
    """
    Standardizes weight clipping and normalization based on cluster_cap.
    Uses institutional simplex projection to ensure diversity without cash drag.
    (Pillar 3: Diversity Compliance).
    """
    if flat_weights.empty:
        return

    from tradingview_scraper.portfolio_engines.base import _project_capped_simplex

    cluster_cap = float(settings.cluster_cap)
    w_sum_abs = float(flat_weights["Weight"].sum())

    if w_sum_abs > 1e-6:
        # Enforce cap using Simplex Projection to maintain sum=1.0 (or original sum)
        weights_np = flat_weights["Weight"].values
        capped_weights = _project_capped_simplex(weights_np / w_sum_abs, cluster_cap)

        flat_weights["Weight"] = capped_weights * w_sum_abs

        # Adjust Net_Weight accordingly (preserving direction)
        directions = flat_weights["Net_Weight"].apply(lambda x: 1.0 if x >= 0 else -1.0)
        flat_weights["Net_Weight"] = flat_weights["Weight"] * directions
