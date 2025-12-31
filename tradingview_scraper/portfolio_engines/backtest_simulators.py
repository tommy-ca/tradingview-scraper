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
        settings = get_settings()
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

        w_target = cast(pd.Series, w / normalizer)

        # Borrow costs application
        returns_mtx = test_data[symbols].copy()
        total_borrow_cost = 0.0
        num_days = len(returns_mtx)
        if settings.features.feat_short_costs:
            borrow_daily = settings.features.short_borrow_cost / 252.0
            for sym in symbols:
                if w_target[sym] < 0:
                    returns_mtx[sym] = returns_mtx[sym] - borrow_daily
                    total_borrow_cost += abs(float(w_target[sym])) * borrow_daily * num_days

        # Simulation Mode: Daily Reset vs. Window Drift
        if settings.features.feat_rebalance_mode == "window":
            # Set weights on Day 1, let them drift
            daily_returns_list = []
            curr_w = w_target.values
            for i in range(len(returns_mtx)):
                r_day = returns_mtx.iloc[i].values
                # Portfolio return for the day
                port_ret = np.sum(curr_w * r_day)
                daily_returns_list.append(port_ret)
                # Update weights for next day (Drift)
                # w_next = w_prev * (1 + r_asset) / (1 + r_port)
                # Note: we handle the case where port_ret is -1.0 (bankruptcy)
                denom = 1.0 + port_ret
                if abs(denom) < 1e-9:
                    curr_w = np.zeros_like(curr_w)
                else:
                    curr_w = curr_w * (1.0 + r_day) / denom
            daily_returns = pd.Series(daily_returns_list, index=test_data.index)
        else:
            # Daily Rebalancing Logic (Legacy/Reset)
            daily_np = (np.asarray(returns_mtx, dtype=float) * w_target.values).sum(axis=1)
            daily_returns = pd.Series(daily_np, index=test_data.index).dropna()

        res = calculate_performance_metrics(daily_returns)
        res["daily_returns"] = daily_returns
        res["borrow_costs"] = total_borrow_cost

        # Idealized Turnover
        if initial_holdings is not None:
            combined_index = initial_holdings.index.union(w_target.index)
            h_start = initial_holdings.reindex(combined_index, fill_value=0.0)
            h_target = w_target.reindex(combined_index, fill_value=0.0)
            res["turnover"] = float(np.abs(h_target.to_numpy() - h_start.to_numpy()).sum()) / 2.0
        else:
            res["turnover"] = 1.0

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

        # Consistent Timezone Handling
        if not isinstance(returns.index, pd.DatetimeIndex):
            returns.index = pd.to_datetime(returns.index)
        if returns.index.tz is None:
            returns.index = returns.index.tz_localize("UTC")
        else:
            returns.index = returns.index.tz_convert("UTC")

        # Start and end times must match the (possibly localized) index
        start_t = returns.index[0]
        end_t = returns.index[-1]

        cash_key = settings.backtest_cash_asset
        returns[cash_key] = 0.0
        returns = returns.fillna(0.0)

        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
        available = [s for s in weights_df["Symbol"] if s in test_data.columns]
        w_sub = weights_df[weights_df["Symbol"].isin(available)].copy()
        w_series = w_sub.set_index("Symbol")[weight_col].astype(float)

        abs_sum = float(w_series.abs().sum())
        if abs_sum > 1.0:
            w_series = w_series / abs_sum

        w_series = w_series.reindex(returns.columns, fill_value=0.0)
        w_series[cash_key] = 1.0 - w_series.drop(cash_key).abs().sum()
        w_series = w_series.fillna(0.0)

        # Policy Selection: Daily Reset vs. Window Drift
        # For CVX, we use FixedWeights(Series) which is robust.
        # Window drift is better modeled by PeriodicRebalance, but it's currently unstable in 1.5.1.
        policy = self.cvp.FixedWeights(w_series)

        # Costs
        cost_list: List[Any] = [self.cvp.TransactionCost(a=settings.backtest_slippage + settings.backtest_commission)]
        if settings.features.feat_short_costs:
            cost_list.append(self.cvp.HoldingCost(short_fees=settings.features.short_borrow_cost))

        # Initial weights for the very first trade (transition from previous window)
        h_init = None
        if initial_holdings is not None:
            h_init = initial_holdings.reindex(returns.columns, fill_value=0.0)
            h_sum = h_init.abs().sum()
            if h_sum > 0:
                h_init = h_init / h_sum

        try:
            simulator = self.cvp.MarketSimulator(returns=returns, costs=cost_list, cash_key=cash_key, min_history=pd.Timedelta(days=0))
            result = simulator.backtest(policy, start_time=start_t, end_time=end_t, h=h_init)

            realized_returns = result.v.pct_change().dropna()

            res = calculate_performance_metrics(realized_returns)
            res["daily_returns"] = realized_returns
            # Return final weights for next window
            res["final_weights"] = result.w.iloc[-1]
            res["turnover"] = float(result.turnover.sum())  # Total turnover for the period

            # Extract borrow costs if present
            # cvxportfolio costs are Series indexed by time
            # result.costs is a list of costs series if multiple costs
            b_cost = 0.0
            if settings.features.feat_short_costs and len(cost_list) > 1:
                # Assuming HoldingCost is the second one
                # Actually it's safer to look at result.costs
                # result.costs is a DataFrame in newer versions or list
                try:
                    # Sum the specific cost series
                    # If it's a DataFrame, it might have columns
                    if isinstance(result.costs, pd.DataFrame):
                        # Filter columns that look like holding costs
                        h_cols = [c for c in result.costs.columns if "HoldingCost" in str(c)]
                        if h_cols:
                            b_cost = float(result.costs[h_cols].sum().sum())
                except:
                    pass
            res["borrow_costs"] = b_cost
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
