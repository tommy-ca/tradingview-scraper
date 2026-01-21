import logging
from typing import List, Tuple

import numpy as np
import pandas as pd

from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.filters.base import BaseFilter
from tradingview_scraper.settings import get_settings

logger = logging.getLogger(__name__)


class SpectralFilter(BaseFilter):
    """
    Spectral vetoes: Entropy, Hurst, and Efficiency ratio filters.
    """

    @property
    def name(self) -> str:
        return "spectral"

    def apply(self, context: SelectionContext) -> Tuple[SelectionContext, List[str]]:
        vetoed = []
        s = get_settings()

        # Load thresholds from context params or global settings
        entropy_max = context.params.get("entropy_max_threshold", s.features.entropy_max_threshold)
        hurst_min = context.params.get("hurst_random_walk_min", s.features.hurst_random_walk_min)
        hurst_max = context.params.get("hurst_random_walk_max", s.features.hurst_random_walk_max)
        efficiency_min = context.params.get("efficiency_min_threshold", s.features.efficiency_min_threshold)

        # We assume spectral metrics are stored in inference_outputs or feature_store
        # (This depends on where the pipeline calculates them)
        metrics = context.inference_outputs

        for symbol in context.returns_df.columns:
            if symbol not in metrics.columns:
                continue

            pe = metrics.loc["entropy", symbol] if "entropy" in metrics.index else None
            er = metrics.loc["efficiency", symbol] if "efficiency" in metrics.index else None
            h = metrics.loc["hurst_clean", symbol] if "hurst_clean" in metrics.index else None

            # 1. Entropy Veto
            if pe is not None and not np.isnan(pe) and pe > entropy_max:
                vetoed.append(symbol)
                context.log_event("Filter", "Veto", {"symbol": symbol, "reason": f"High Entropy ({pe:.4f})"})
                continue

            # 2. Efficiency Veto
            if er is not None and not np.isnan(er) and er < efficiency_min:
                vetoed.append(symbol)
                context.log_event("Filter", "Veto", {"symbol": symbol, "reason": f"Low Efficiency ({er:.4f})"})
                continue

            # 3. Hurst (Random Walk) Veto
            if h is not None and not np.isnan(h):
                # Is it a benchmark? Benchmarks are exempt.
                meta = next((c for c in context.raw_pool if c.get("symbol") == symbol), {})
                if not meta.get("is_benchmark", False):
                    if hurst_min < h < hurst_max:
                        vetoed.append(symbol)
                        context.log_event("Filter", "Veto", {"symbol": symbol, "reason": f"Random Walk (H={h:.4f})"})

        return context, vetoed
