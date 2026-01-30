import logging
from typing import List, Tuple

import numpy as np

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.filters.base import BaseFilter

logger = logging.getLogger("pipelines.selection.filters.trend")


@StageRegistry.register(id="selection.filter.trend", name="Trend Regime Filter", description="MTF Trend & Signal Regime Gate", category="selection", tags=["filter"])
class TrendRegimeFilter(BaseFilter):
    """
    Pillar 1 Filter: Enforces Secular Trend Regime & Signal Recency.

    Logic:
    - Long: Close > SMA200 (Regime) AND VWMA20 crosses above SMA200 (Signal).
    - Short: Close < SMA200 (Regime) AND VWMA20 crosses below SMA200 (Signal).

    Uses 'strict_signal' to toggle the Crossover check (vs just Regime check).
    """

    def __init__(self, strict_regime: bool = True, strict_signal: bool = True, lookback: int = 5, regime_source: str = "close", threshold: float = 0.0):
        self.strict_regime = strict_regime
        self.strict_signal = strict_signal
        self.lookback = lookback
        self.regime_source = regime_source
        self.threshold = threshold

    @property
    def name(self) -> str:
        return "trend_regime"

    def apply(self, context: SelectionContext) -> Tuple[SelectionContext, List[str]]:
        features = context.feature_store
        candidates = context.candidates

        vetoed = set()

        if features.empty:
            logger.warning("TrendRegimeFilter: Feature store empty. Passing all.")
            return context, list(vetoed)

        for cand in candidates:
            symbol = str(cand.get("symbol"))
            direction = str(cand.get("direction", "LONG")).upper()

            # Check if features exist
            try:
                # Expecting MultiIndex (symbol, feature)
                hist = features[symbol]

                sma_200 = hist["sma_200"]
                vwma_20 = hist["vwma_20"]

                # Determine Regime Source
                if self.regime_source == "vwma":
                    price_proxy = vwma_20
                elif self.regime_source == "sma_50":
                    price_proxy = hist["sma_50"] if "sma_50" in hist.columns else vwma_20
                else:  # Default 'close'
                    price_proxy = hist["close"] if "close" in hist.columns else vwma_20

            except KeyError:
                logger.debug(f"TrendFilter: Missing features for {symbol}. Vetoing.")
                vetoed.add(symbol)
                context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Missing trend features"})
                continue

            # 1. Regime Check (Smoothed with Threshold)
            # Long: Proxy > SMA * (1 + threshold)
            # Short: Proxy < SMA * (1 - threshold)

            current_proxy = price_proxy.iloc[-1]
            current_base = sma_200.iloc[-1]

            is_bull = False
            if direction == "LONG":
                is_bull = current_proxy > (current_base * (1.0 + self.threshold))
            else:
                # For Short, 'is_bull' means Bear regime if we invert logic?
                # Let's keep is_bull as "Is in Uptrend".
                # Short requires !is_bull (Downtrend).
                # Downtrend: Proxy < SMA * (1 - threshold)
                is_uptrend = current_proxy > (current_base * (1.0 + self.threshold))
                is_downtrend = current_proxy < (current_base * (1.0 - self.threshold))

                # Logic map:
                # Dir=Long -> Require is_uptrend
                # Dir=Short -> Require is_downtrend

            regime_pass = True
            if self.strict_regime:
                if direction == "LONG":
                    if not (current_proxy > current_base * (1.0 + self.threshold)):
                        regime_pass = False
                elif direction == "SHORT":
                    if not (current_proxy < current_base * (1.0 - self.threshold)):
                        regime_pass = False

            if not regime_pass:
                logger.info(f"Veto {symbol}: Bad Regime (Dir={direction}, Val={current_proxy:.4f}, Base={current_base:.4f})")
                vetoed.add(symbol)
                context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Bad Trend Regime", "direction": direction})
                continue

            # 2. Signal Check (Crossover)
            if self.strict_signal:
                # Check last N bars for cross
                cross_detected = False
                # Diff = Fast - Slow
                diff = vwma_20 - sma_200

                # Check recent window
                recent = diff.iloc[-self.lookback :]

                # Cross Logic: Sign change
                # We need at least 2 points
                if len(recent) >= 2:
                    signs = np.sign(recent)

                    if direction == "LONG":
                        # Crossing UP: Negative -> Positive
                        # Look for any instance where prev < 0 and curr > 0
                        has_cross = ((signs.shift(1) < 0) & (signs > 0)).any()
                        if has_cross:
                            cross_detected = True
                    else:
                        # Crossing DOWN: Positive -> Negative
                        has_cross = ((signs.shift(1) > 0) & (signs < 0)).any()
                        if has_cross:
                            cross_detected = True

                if not cross_detected:
                    logger.debug(f"Veto {symbol}: No Signal (Dir={direction})")
                    vetoed.add(symbol)
                    context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "No Crossover Signal", "lookback": self.lookback})
                    continue

        return context, list(vetoed)

        for cand in candidates:
            symbol = str(cand.get("symbol"))
            direction = str(cand.get("direction", "LONG")).upper()

            # Check if features exist
            try:
                # Expecting MultiIndex (symbol, feature)
                hist = features[symbol]

                sma_200 = hist["sma_200"]
                vwma_20 = hist["vwma_20"]

                # Use SMA50 as proxy for Price if Close missing (robustness)
                price_proxy = hist["sma_50"] if "sma_50" in hist.columns else sma_200
                if "close" in hist.columns:
                    price_proxy = hist["close"]

            except KeyError:
                logger.debug(f"TrendFilter: Missing features for {symbol}. Vetoing.")
                vetoed.add(symbol)
                context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Missing trend features"})
                continue

            # 1. Regime Check
            is_bull = price_proxy.iloc[-1] > sma_200.iloc[-1]

            regime_pass = True
            if self.strict_regime:
                if direction == "LONG" and not is_bull:
                    regime_pass = False
                elif direction == "SHORT" and is_bull:
                    regime_pass = False

            if not regime_pass:
                logger.info(f"Veto {symbol}: Bad Regime (Dir={direction}, Bull={is_bull})")
                vetoed.add(symbol)
                context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "Bad Trend Regime", "is_bull": is_bull, "direction": direction})
                continue

            # 2. Signal Check (Crossover)
            if self.strict_signal:
                # Check last N bars for cross
                cross_detected = False
                # Diff = Fast - Slow
                diff = vwma_20 - sma_200

                # Check recent window
                recent = diff.iloc[-self.lookback :]

                # Cross Logic: Sign change
                # We need at least 2 points
                if len(recent) >= 2:
                    signs = np.sign(recent)
                    # Detect change: diff of signs != 0

                    if direction == "LONG":
                        # Crossing UP: Negative -> Positive
                        # Look for any instance where prev < 0 and curr > 0
                        has_cross = ((signs.shift(1) < 0) & (signs > 0)).any()
                        if has_cross:
                            cross_detected = True
                    else:
                        # Crossing DOWN: Positive -> Negative
                        has_cross = ((signs.shift(1) > 0) & (signs < 0)).any()
                        if has_cross:
                            cross_detected = True

                if not cross_detected:
                    logger.debug(f"Veto {symbol}: No Signal (Dir={direction})")
                    vetoed.add(symbol)
                    context.log_event("Filter", "Veto", {"symbol": symbol, "reason": "No Crossover Signal", "lookback": self.lookback})
                    continue

        return context, list(vetoed)
