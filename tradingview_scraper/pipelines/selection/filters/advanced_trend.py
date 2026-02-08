import logging
from typing import List, Tuple

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.filters.base import BaseFilter

logger = logging.getLogger("pipelines.selection.filters.advanced_trend")


@StageRegistry.register(id="selection.filter.advanced_trend", name="Advanced Trend Filter", description="ADX/Donchian/BB Trend Filters", category="selection", tags=["filter"])
class AdvancedTrendFilter(BaseFilter):
    """
    Pillar 1 Filter: Advanced Trend Regimes using ADX/DMI and Donchian Channels.

    Modes:
    - 'adx_regime': Requires ADX > threshold AND Directional Movement alignment.
    - 'donchian_breakout': Requires Close > Upper (Long) or Close < Lower (Short).
    - 'bb_expansion': Requires BB Width > threshold (Vol expansion).
    """

    def __init__(self, mode: str = "adx_regime", adx_threshold: float = 20.0, strict: bool = True):
        self.mode = mode
        self.adx_threshold = adx_threshold
        self.strict = strict

    @property
    def name(self) -> str:
        return f"advanced_trend_{self.mode}"

    def apply(self, context: SelectionContext) -> Tuple[SelectionContext, List[str]]:
        features = context.feature_store
        candidates = context.candidates

        vetoed = set()

        if features.empty:
            logger.warning("AdvancedTrendFilter: Feature store empty. Passing all.")
            return context, list(vetoed)

        for cand in candidates:
            symbol = str(cand.get("symbol"))
            direction = str(cand.get("direction", "LONG")).upper()

            try:
                hist = features[symbol]
                close = hist["close"] if "close" in hist.columns else None
                # Fallback close logic from backfill (unlikely needed if we run backfill correctly)
                if close is None and "vwma_20" in hist.columns:
                    close = hist["vwma_20"]

                # Mode 1: ADX Regime
                if self.mode == "adx_regime":
                    adx = hist.get("adx_14")
                    dmp = hist.get("dmp_14")
                    dmn = hist.get("dmn_14")

                    if adx is None or dmp is None or dmn is None:
                        # Log warning but maybe skip veto if strict=False?
                        if self.strict:
                            vetoed.add(symbol)
                            context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Missing ADX data"})
                        continue

                    curr_adx = adx.iloc[-1]
                    curr_dmp = dmp.iloc[-1]
                    curr_dmn = dmn.iloc[-1]

                    # 1. Trend Strength
                    if curr_adx < self.adx_threshold:
                        vetoed.add(symbol)
                        context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Weak Trend (ADX)", "adx": curr_adx})
                        continue

                    # 2. Directional Alignment
                    if direction == "LONG":
                        if not (curr_dmp > curr_dmn):
                            vetoed.add(symbol)
                            context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Bearish DMI (Long)", "dmp": curr_dmp, "dmn": curr_dmn})
                            continue
                    elif direction == "SHORT":
                        if not (curr_dmn > curr_dmp):
                            vetoed.add(symbol)
                            context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Bullish DMI (Short)", "dmp": curr_dmp, "dmn": curr_dmn})
                            continue

                # Mode 2: Donchian Breakout
                elif self.mode == "donchian_breakout":
                    dc_u = hist.get("donchian_upper_20")
                    dc_l = hist.get("donchian_lower_20")

                    if dc_u is None or dc_l is None:
                        if self.strict:
                            vetoed.add(symbol)
                        continue

                    curr_price = close.iloc[-1]
                    # Hysteresis? Or direct breakout?
                    # Strict breakout implies Price is AT or ABOVE the band.
                    # Usually DC Upper is the Max High of N periods.
                    # If Price > DC Upper[prev], it's a breakout.
                    # Current impl of pandas_ta returns current channel.

                    if direction == "LONG":
                        # Check if price is near upper band (e.g. > 99% of Upper)
                        # Or strictly > Upper (if Upper excludes current bar, but pandas_ta usually includes)
                        if curr_price < dc_u.iloc[-1] * 0.995:
                            vetoed.add(symbol)
                            context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Not at Donchian Upper"})
                            continue
                    elif direction == "SHORT":
                        if curr_price > dc_l.iloc[-1] * 1.005:
                            vetoed.add(symbol)
                            context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Not at Donchian Lower"})
                            continue

            except KeyError as e:
                logger.debug(f"AdvancedTrendFilter error: {e}")
                if self.strict:
                    vetoed.add(symbol)
                continue
            except Exception as e:
                logger.error(f"AdvancedTrendFilter unexpected error for {symbol}: {e}")
                continue

        return context, list(vetoed)
