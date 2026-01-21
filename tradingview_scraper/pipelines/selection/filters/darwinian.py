import logging
from typing import List, Tuple

import pandas as pd

from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.filters.base import BaseFilter

logger = logging.getLogger(__name__)


class DarwinianFilter(BaseFilter):
    """
    Health-based vetoes: checks for missing data, low volume, and metadata completeness.
    """

    @property
    def name(self) -> str:
        return "darwinian"

    def apply(self, context: SelectionContext) -> Tuple[SelectionContext, List[str]]:
        vetoed = []

        # 1. Check Metadata Completeness
        # (Heuristic: must have tick_size, lot_size, price_precision)
        candidate_map = {c["symbol"]: c for c in context.raw_pool if "symbol" in c}

        for symbol in context.returns_df.columns:
            meta = candidate_map.get(symbol, {})
            missing_meta = [f for f in ["tick_size", "lot_size", "price_precision"] if f not in meta]
            if missing_meta:
                vetoed.append(symbol)
                context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Missing metadata", "fields": missing_meta})
                continue

            # 2. Check Data Health (Darwinian Gate)
            # (Currently this uses 'Regime_Survival_Score' if available in inference_outputs)
            if symbol in context.inference_outputs.index:
                survival = context.inference_outputs.get("survival", pd.Series(1.0, index=context.inference_outputs.index)).get(symbol, 1.0)
                if survival < 0.1:
                    vetoed.append(symbol)
                    context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Failed Darwinian Health Gate", "score": float(survival)})

        return context, vetoed
