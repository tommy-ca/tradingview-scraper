import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.metrics import calculate_performance_metrics

logger = logging.getLogger("backtest_simulators")


def _calculate_standard_turnover(w_target: pd.Series, h_init: Optional[pd.Series]) -> float:
    """
    Calculates one-way turnover for a rebalance from h_init to w_target.
    If h_init is None, assumes 100% buy-in from cash.
    """
    w1 = w_target.copy()
    if "cash" not in w1.index:
        w1["cash"] = max(0.0, 1.0 - w1.sum())

    if h_init is None:
        w0 = pd.Series(0.0, index=w1.index)
        w0["cash"] = 1.0
    else:
        w0 = h_init.copy()
        if "cash" not in w0.index:
            w0["cash"] = max(0.0, 1.0 - w0.sum())

    all_assets = sorted(list(set(w1.index) | set(w0.index)))
    w1 = w1.reindex(all_assets, fill_value=0.0)
    w0 = w0.reindex(all_assets, fill_value=0.0)

    return float((w1 - w0).abs().sum()) / 2.0


class BaseSimulator(ABC):
    """Abstract base class for all backtest simulators."""

    @abstractmethod
    def simulate(
        self,
        returns: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        """
        Runs a simulation over the test_data period.
        """
        pass


class ReturnsSimulator(BaseSimulator):
    """
    Standard simulator using direct returns summation.
    Includes estimated friction based on turnover.
    """

    def simulate(
        self,
        returns: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        settings = get_settings()
        target_len = 20
        returns_to_use = returns.iloc[:target_len] if len(returns) > target_len else returns

        w_target = weights_df.set_index("Symbol")["Weight"].astype(float)
        if "cash" not in w_target.index:
            w_target["cash"] = max(0.0, 1.0 - w_target.sum())

        rebalance_mode = settings.features.feat_rebalance_mode
        tolerance_enabled = settings.features.feat_rebalance_tolerance
        drift_limit = settings.features.rebalance_drift_limit
        total_rate = settings.backtest_slippage + settings.backtest_commission

        turnover_t0 = _calculate_standard_turnover(w_target, initial_holdings)
        friction_t0 = turnover_t0 * 2.0 * total_rate

        daily_p_rets = []
        current_weights = w_target.copy()
        total_turnover = turnover_t0

        for t in range(len(returns_to_use)):
            returns_t = returns_to_use.iloc[t].reindex(current_weights.index, fill_value=0.0)
            p_ret_t = (current_weights * returns_t).sum()

            drift_weights = current_weights * (1 + returns_t)
            drift_weights = drift_weights / drift_weights.sum()

            friction_t = 0.0
            if rebalance_mode == "daily":
                turnover_t = _calculate_standard_turnover(w_target, drift_weights)
                friction_t = turnover_t * 2.0 * total_rate
                current_weights = w_target.copy()
                total_turnover += turnover_t
            elif tolerance_enabled:
                drift_dist = (drift_weights - w_target).abs().sum() / 2.0
                if drift_dist > drift_limit:
                    turnover_t = _calculate_standard_turnover(w_target, drift_weights)
                    friction_t = turnover_t * 2.0 * total_rate
                    current_weights = w_target.copy()
                    total_turnover += turnover_t
                else:
                    current_weights = drift_weights
            else:
                current_weights = drift_weights

            net_ret_t = p_ret_t - friction_t
            if t == 0:
                net_ret_t -= friction_t0
            daily_p_rets.append(net_ret_t)

        p_returns = pd.Series(daily_p_rets, index=returns_to_use.index)
        res = calculate_performance_metrics(p_returns)
        res["daily_returns"] = p_returns
        res["turnover"] = total_turnover
        res["final_weights"] = current_weights
        return res


class CVXPortfolioSimulator(BaseSimulator):
    """High-fidelity friction simulator using CVXPortfolio."""

    def __init__(self):
        try:
            import cvxportfolio as cvp
            from cvxportfolio.policies import Policy

            self.cvp = cvp
            self.Policy = Policy
        except ImportError:
            raise ImportError("cvxportfolio not installed.")

    def simulate(
        self,
        returns: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        settings = get_settings()
        cash_key = "cash"

        start_t = returns.index[0]
        end_t = returns.index[-1]
        universe = list(returns.columns)
        if cash_key not in universe:
            universe.append(cash_key)

        w_target = weights_df.set_index("Symbol")["Weight"].astype(float).reindex(universe, fill_value=0.0)
        non_cash_sum = float(w_target.drop(index=[cash_key]).abs().sum())
        w_target[cash_key] = max(0.0, 1.0 - non_cash_sum)
        w_target = w_target.fillna(0.0)

        rebalance_mode = settings.features.feat_rebalance_mode

        h_init = pd.Series(0.0, index=universe, dtype=np.float64)
        if initial_holdings is not None:
            h_init = initial_holdings.reindex(universe, fill_value=0.0).astype(np.float64)
            h_sum = float(h_init.abs().sum())
            if h_sum > 0:
                h_init = h_init / h_sum
            else:
                h_init[cash_key] = 1.0
        else:
            h_init[cash_key] = 1.0

        if rebalance_mode == "daily":
            policy = self.cvp.FixedWeights(w_target)
        else:
            trades = pd.DataFrame(0.0, index=returns.index, columns=pd.Index(universe))
            trades.iloc[0] = w_target - h_init
            policy = self.cvp.FixedTrades(trades)

        cost_list: List[Any] = [self.cvp.TransactionCost(a=settings.backtest_slippage + settings.backtest_commission)]
        if settings.features.feat_short_costs:
            cost_list.append(self.cvp.HoldingCost(short_fees=settings.features.short_borrow_cost))

        try:
            returns_cvx = returns.astype(np.float64).clip(-0.5, 2.0)
            simulator = self.cvp.MarketSimulator(returns=returns_cvx, costs=cost_list, cash_key=cash_key, min_history=pd.Timedelta(days=0))
            result = simulator.backtest(policy, start_time=start_t, end_time=end_t, h=h_init)

            realized_returns = result.v.pct_change().dropna()
            realized_returns.index = returns.index[: len(realized_returns)]

            if len(realized_returns) > 20:
                realized_returns = realized_returns.iloc[:20]

            res = calculate_performance_metrics(realized_returns)
            res.update(
                {
                    "daily_returns": realized_returns,
                    "final_weights": result.w.iloc[-1],
                    "turnover": _calculate_standard_turnover(w_target, initial_holdings) if rebalance_mode != "daily" else float(result.turnover.sum()) * 2.0,
                }
            )
            return res
        except Exception as e:
            logger.error(f"cvxportfolio failed: {e}")
            return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)


class VectorBTSimulator(BaseSimulator):
    """High-performance vectorized simulator using VectorBT."""

    def simulate(
        self,
        returns: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        try:
            import vectorbt as vbt
        except ImportError:
            raise ImportError("vectorbt not installed.")
        settings = get_settings()

        rebalance_mode = settings.features.feat_rebalance_mode
        w_series = weights_df.set_index("Symbol")["Weight"].astype(float)

        target_len = 20
        returns_to_use = returns.iloc[:target_len] if len(returns) > target_len else returns
        prices = (1.0 + returns_to_use[w_series.index]).cumprod()

        if rebalance_mode == "daily":
            w_df = pd.DataFrame([w_series.values] * len(prices), columns=w_series.index, index=prices.index)
        else:
            w_df = pd.DataFrame(np.nan, columns=w_series.index, index=prices.index)
            w_df.iloc[0] = w_series.values

        portfolio = vbt.Portfolio.from_orders(
            close=prices, size=w_df, size_type="target_percent", fees=settings.backtest_slippage + settings.backtest_commission, freq="D", init_cash=100.0, group_by=True
        )
        p_returns = portfolio.returns()
        res = calculate_performance_metrics(p_returns)
        res["daily_returns"] = p_returns
        res["turnover"] = _calculate_standard_turnover(w_series, initial_holdings)
        return res


def build_simulator(name: str) -> BaseSimulator:
    if name == "custom":
        return ReturnsSimulator()
    elif name == "cvxportfolio":
        return CVXPortfolioSimulator()
    elif name == "vectorbt":
        return VectorBTSimulator()
    elif name == "nautilus":
        return NautilusSimulator()
    raise ValueError(f"Unknown simulator: {name}")


class NautilusSimulator(BaseSimulator):
    """Event-driven high-fidelity simulator using NautilusTrader (Placeholder)."""

    def simulate(self, returns: pd.DataFrame, weights_df: pd.DataFrame, initial_holdings: Optional[pd.Series] = None) -> Dict[str, Any]:
        return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)
