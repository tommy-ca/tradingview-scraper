from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, cast

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
    ) -> Dict[str, Any]:
        """
        Simulate portfolio performance over a test window.
        Returns a dictionary with 'daily_returns' and other metrics.
        """
        pass


class ReturnsSimulator(BaseSimulator):
    """
    Internal baseline simulator.
    Idealized returns based on direct dot-product of weights and daily returns.
    """

    def simulate(
        self,
        test_data: pd.DataFrame,
        weights_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        weights_series = weights_df.set_index("Symbol")[weight_col].astype(float)
        symbols = [s for s in weights_series.index if s in test_data.columns]

        empty_res = {
            "total_return": 0.0,
            "realized_vol": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "var_95": None,
            "cvar_95": None,
            "daily_returns": pd.Series(dtype=float),
        }

        if not symbols:
            return empty_res

        # Re-normalize weights for available symbols
        w = weights_series[symbols].astype(float)
        w_np = np.asarray(w, dtype=float)
        if weight_col == "Net_Weight":
            normalizer = float(np.sum(np.abs(w_np)))
        else:
            normalizer = float(np.sum(w_np))

        if normalizer <= 0:
            return empty_res

        w_np = w_np / normalizer

        # Dot product of returns and weights
        daily_np = (np.asarray(test_data[symbols], dtype=float) * w_np).sum(axis=1)
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
            logger.warning("cvxportfolio not installed. CvxPortfolioSimulator unavailable.")

    def simulate(
        self,
        test_data: pd.DataFrame,
        weights_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        if self.cvp is None:
            # Fallback to ReturnsSimulator if cvxportfolio is missing
            return ReturnsSimulator().simulate(test_data, weights_df)

        settings = get_settings()

        # 1. Prepare Data
        returns = test_data.copy()
        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        # Ensure UTC timezone for cvxportfolio compatibility
        if returns.index.tz is None:
            returns.index = returns.index.tz_localize("UTC")
        else:
            returns.index = returns.index.tz_convert("UTC")

        cash_key = settings.backtest_cash_asset
        returns[cash_key] = 0.0

        # 2. Define Policy (Fixed weights from optimizer)
        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        available_symbols = [s for s in weights_df["Symbol"] if s in test_data.columns]
        weights_sub = weights_df[weights_df["Symbol"].isin(available_symbols)].copy()

        w_series = weights_sub.set_index("Symbol")[weight_col].astype(float)

        # Ensure sum of abs weights <= 1.0 (long-only or long-short)
        abs_sum = float(w_series.abs().sum())
        if abs_sum > 1.0:
            w_series = w_series / abs_sum

        # Reindex to match the returns DataFrame (which has cash_key)
        w_series = w_series.reindex(returns.columns, fill_value=0.0)

        # Cash weight
        w_series[cash_key] = 1.0 - w_series.drop(cash_key).abs().sum()

        policy = self.cvp.FixedWeights(w_series)

        # 3. Define Simulator with Friction
        linear_friction = settings.backtest_slippage + settings.backtest_commission

        # cvxportfolio has a default min_history of 252 days.
        try:
            simulator = self.cvp.MarketSimulator(returns=returns, costs=[self.cvp.TransactionCost(a=linear_friction)], cash_key=cash_key, min_history=pd.Timedelta(days=0))
        except Exception:
            simulator = self.cvp.MarketSimulator(returns=returns, costs=[self.cvp.TransactionCost(a=linear_friction)], cash_key=cash_key)

        # 4. Run Simulation
        try:
            result = simulator.backtest(policy, start_time=test_data.index[0], end_time=test_data.index[-1])
            v = result.v  # portfolio value over time
            realized_returns = v.pct_change().dropna()

            res = calculate_performance_metrics(realized_returns)
            res["daily_returns"] = realized_returns
            return res

        except Exception as e:
            logger.error(f"cvxportfolio simulation failed: {e}")
            return ReturnsSimulator().simulate(test_data, weights_df)


class VectorBTSimulator(BaseSimulator):
    """
    High-performance simulator using vectorbt.
    Vectorized returns-based rebalancing with friction modeling.
    """

    def __init__(self):
        try:
            import vectorbt as vbt

            self.vbt = vbt
        except ImportError:
            self.vbt = None
            logger.warning("vectorbt not installed. VectorBTSimulator unavailable.")

    def simulate(
        self,
        test_data: pd.DataFrame,
        weights_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        if self.vbt is None:
            return ReturnsSimulator().simulate(test_data, weights_df)

        settings = get_settings()

        # 1. Align and Filter
        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        available = [s for s in weights_df["Symbol"] if s in test_data.columns]
        if not available:
            return ReturnsSimulator().simulate(test_data, weights_df)

        w_series = weights_df.set_index("Symbol")[weight_col].reindex(available).fillna(0.0)
        abs_sum = float(w_series.abs().sum())
        if abs_sum > 1.0:
            w_series = w_series / abs_sum

        rets = test_data[available].fillna(0.0)

        # 2. Build Portfolio
        try:
            # Rebalancing once at the start of the window
            vbt_any = cast(Any, self.vbt)
            pf = vbt_any.Portfolio.from_returns(
                rets,
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
            logger.error(f"vectorbt simulation failed: {e}")
            return ReturnsSimulator().simulate(test_data, weights_df)


def build_simulator(name: str = "custom") -> BaseSimulator:
    """Factory to build the requested simulator."""
    n = name.lower()
    if n == "cvxportfolio":
        return CvxPortfolioSimulator()
    if n == "vectorbt":
        return VectorBTSimulator()
    return ReturnsSimulator()
