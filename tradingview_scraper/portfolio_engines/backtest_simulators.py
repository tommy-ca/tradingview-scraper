from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from tradingview_scraper.settings import get_settings

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

        if len(daily_returns) == 0:
            return empty_res

        var_95 = float(daily_returns.quantile(0.05))
        tail = daily_returns[daily_returns <= var_95]
        cvar_95 = float(tail.mean()) if len(tail) else var_95

        total_return = (1 + daily_returns).prod() - 1
        realized_vol = daily_returns.std() * np.sqrt(252)
        sharpe = (daily_returns.mean() * 252) / (realized_vol + 1e-9)

        cum_ret = (1 + daily_returns).cumprod()
        running_max = cum_ret.cummax()
        drawdown = (cum_ret - running_max) / (running_max + 1e-12)
        max_drawdown = float(drawdown.min())

        return {
            "total_return": float(total_return),
            "realized_vol": float(realized_vol),
            "sharpe": float(sharpe),
            "max_drawdown": max_drawdown,
            "var_95": var_95,
            "cvar_95": cvar_95,
            "daily_returns": daily_returns,
        }


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
        # cvxportfolio expects returns and optionally volumes/prices.
        # For simplicity in this bridge, we use the provided returns.
        # We add a cash asset (stablecoin) as required by cvxportfolio.

        returns = test_data.copy()
        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)

        # Ensure UTC timezone for cvxportfolio compatibility
        if returns.index.tz is None:
            returns.index = returns.index.tz_localize("UTC")
        else:
            returns.index = returns.index.tz_convert("UTC")

        cash_key = settings.backtest_cash_asset
        # Minimal returns for cash (0.0 unless we have data)
        returns[cash_key] = 0.0

        # 2. Define Policy (Fixed weights from optimizer)
        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        # Only use symbols present in test_data
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
        # We use transaction cost and holding cost models
        tcost = self.cvp.TransactionCost(
            a=settings.backtest_slippage,
            b=0.0,  # No non-linear impact for now as we don't pass volumes
        )

        # Add commission as a separate term if needed, or bundle in 'a'
        # cvxportfolio doesn't have a direct 'commission' param in TCost,
        # but 'a' is the linear term (half-spread + commission).
        linear_friction = settings.backtest_slippage + settings.backtest_commission

        # cvxportfolio has a default min_history of 252 days.
        # We need to disable or lower it for short test windows.
        try:
            simulator = self.cvp.MarketSimulator(returns=returns, costs=[self.cvp.TransactionCost(a=linear_friction)], cash_key=cash_key, min_history=pd.Timedelta(days=0))
        except Exception:
            # Fallback if min_history is not supported in this version's init
            simulator = self.cvp.MarketSimulator(returns=returns, costs=[self.cvp.TransactionCost(a=linear_friction)], cash_key=cash_key)

        # 4. Run Simulation
        try:
            # We run for the test_data period
            result = simulator.backtest(policy, start_time=test_data.index[0], end_time=test_data.index[-1])

            # Extract realized daily returns (growth of total value)
            v = result.v  # portfolio value over time
            realized_returns = v.pct_change().dropna()

            # standard metrics
            var_95 = float(realized_returns.quantile(0.05))
            tail = realized_returns[realized_returns <= var_95]
            cvar_95 = float(tail.mean()) if len(tail) else var_95

            total_return = (v.iloc[-1] / v.iloc[0]) - 1
            realized_vol = realized_returns.std() * np.sqrt(252)
            sharpe = (realized_returns.mean() * 252) / (realized_vol + 1e-9)

            cum_ret = (1 + realized_returns).cumprod()
            running_max = cum_ret.cummax()
            drawdown = (cum_ret - running_max) / (running_max + 1e-12)
            max_drawdown = float(drawdown.min())

            return {
                "total_return": float(total_return),
                "realized_vol": float(realized_vol),
                "sharpe": float(sharpe),
                "max_drawdown": max_drawdown,
                "var_95": var_95,
                "cvar_95": cvar_95,
                "daily_returns": realized_returns,
            }
        except Exception as e:
            logger.error(f"cvxportfolio simulation failed: {e}")
            return ReturnsSimulator().simulate(test_data, weights_df)


def build_simulator(name: str = "custom") -> BaseSimulator:
    """Factory to build the requested simulator."""
    if name.lower() == "cvxportfolio":
        return CvxPortfolioSimulator()
    return ReturnsSimulator()
