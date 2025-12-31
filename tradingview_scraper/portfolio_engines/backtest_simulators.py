from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, cast

import numpy as np
import pandas as pd

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.metrics import calculate_performance_metrics

logger = logging.getLogger("backtest_simulators")


class BaseSimulator(ABC):
    """Abstract interface for market simulation backends."""

    @abstractmethod
    def simulate(
        self,
        test_data: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        """
        Simulate portfolio performance over a test window.
        Returns a dictionary with 'daily_returns' and other metrics.
        """
        pass


class ReturnsSimulator(BaseSimulator):
    """
    Internal baseline simulator.
    Models Daily Rebalancing to target weights (fair comparison to CVX).
    """

    def simulate(
        self,
        test_data: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        weights_series = weights_df.set_index("Symbol")[weight_col].astype(float)
        symbols = [s for s in weights_series.index if s in test_data.columns]

        if not symbols:
            return calculate_performance_metrics(pd.Series(dtype=float))

        # Re-normalize weights for available symbols
        w = cast(pd.Series, weights_series[symbols].astype(float))
        normalizer = float(w.abs().sum()) if weight_col == "Net_Weight" else float(w.sum())
        if normalizer <= 0:
            return calculate_performance_metrics(pd.Series(dtype=float))

        w_norm = cast(pd.Series, w / normalizer)

        # Daily Rebalancing Logic:
        # returns_t = sum(w_target * asset_return_t)
        # This assumes the portfolio is reset to the target weights at the end of each day.
        daily_np = (np.asarray(test_data[symbols], dtype=float) * w_norm.values).sum(axis=1)
        daily_returns = pd.Series(daily_np, index=test_data.index).dropna()

        res = calculate_performance_metrics(daily_returns)
        res["daily_returns"] = daily_returns
        return res


class CvxPortfolioSimulator(BaseSimulator):
    """
    High-fidelity simulator using cvxportfolio.
    Models slippage, commissions, and market impact.
    """

    def __init__(self):
        try:
            import cvxportfolio as cvp

            self.cvp = cvp
        except ImportError:
            self.cvp = None
            logger.warning("cvxportfolio not installed.")

    def simulate(
        self,
        test_data: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        if self.cvp is None:
            return ReturnsSimulator().simulate(test_data, weights_df, initial_holdings)

        settings = get_settings()
        returns = test_data.copy()
        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        # Ensure UTC
        if returns.index.tz is None:
            returns.index = returns.index.tz_localize("UTC")
        else:
            returns.index = returns.index.tz_convert("UTC")

        cash_key = settings.backtest_cash_asset
        returns[cash_key] = 0.0

        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        available = [s for s in weights_df["Symbol"] if s in test_data.columns]
        w_sub = weights_df[weights_df["Symbol"].isin(available)].copy()
        w_series = w_sub.set_index("Symbol")[weight_col].astype(float)

        abs_sum = float(w_series.abs().sum())
        if abs_sum > 1.0:
            w_series = w_series / abs_sum

        w_series = w_series.reindex(returns.columns, fill_value=0.0)
        w_series[cash_key] = 1.0 - w_series.drop(cash_key).abs().sum()

        policy = self.cvp.FixedWeights(w_series)
        friction = settings.backtest_slippage + settings.backtest_commission

        # Prepare initial weights for transition modeling
        h_init = None
        if initial_holdings is not None:
            h_init = initial_holdings.reindex(returns.columns, fill_value=0.0)
            # Re-normalize just in case
            h_sum = h_init.abs().sum()
            if h_sum > 0:
                h_init = h_init / h_sum

        try:
            simulator = self.cvp.MarketSimulator(returns=returns, costs=[self.cvp.TransactionCost(a=friction)], cash_key=cash_key, min_history=pd.Timedelta(days=0))
            # If h_init is provided, pass it to backtest as 'h'
            result = simulator.backtest(policy, start_time=test_data.index[0], end_time=test_data.index[-1], h=h_init)
            realized_returns = result.v.pct_change().dropna()

            res = calculate_performance_metrics(realized_returns)
            res["daily_returns"] = realized_returns
            # Return final weights for next window
            res["final_weights"] = result.w.iloc[-1]
            return res
        except Exception as e:
            logger.error(f"cvxportfolio failed: {e}")
            return ReturnsSimulator().simulate(test_data, weights_df, initial_holdings)


class VectorBTSimulator(BaseSimulator):
    """
    High-performance simulator using vectorbt.
    """

    def __init__(self):
        try:
            import vectorbt as vbt

            self.vbt = vbt
        except ImportError:
            self.vbt = None

    def simulate(
        self,
        test_data: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        if self.vbt is None:
            return ReturnsSimulator().simulate(test_data, weights_df, initial_holdings)

        settings = get_settings()
        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        available = [s for s in weights_df["Symbol"] if s in test_data.columns]
        if not available:
            return ReturnsSimulator().simulate(test_data, weights_df, initial_holdings)

        w_series = weights_df.set_index("Symbol")[weight_col].reindex(available).fillna(0.0)
        abs_sum = float(w_series.abs().sum())
        if abs_sum > 1.0:
            w_series = w_series / abs_sum

        try:
            vbt_any = cast(Any, self.vbt)
            pf = vbt_any.Portfolio.from_returns(
                test_data[available].fillna(0.0),
                weights=w_series,
                fees=settings.backtest_commission,
                slippage=settings.backtest_slippage,
                freq="D",
                init_cash=100.0,
            )
            realized_returns = pf.returns()
            res = calculate_performance_metrics(realized_returns)
            res["daily_returns"] = realized_returns
            return res
        except Exception as e:
            logger.error(f"vectorbt failed: {e}")
            return ReturnsSimulator().simulate(test_data, weights_df, initial_holdings)


def build_simulator(name: str = "custom") -> BaseSimulator:
    n = name.lower()
    if n == "cvxportfolio":
        return CvxPortfolioSimulator()
    if n == "vectorbt":
        return VectorBTSimulator()
    return ReturnsSimulator()
