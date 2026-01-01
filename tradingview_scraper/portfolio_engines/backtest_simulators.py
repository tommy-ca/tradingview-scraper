import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.metrics import calculate_performance_metrics

logger = logging.getLogger("backtest_simulators")


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
    """Frictionless lower-bound simulator using direct returns summation."""

    def simulate(
        self,
        returns: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        w_series = weights_df.set_index("Symbol")["Weight"].astype(float)
        available_symbols = [s for s in w_series.index if s in returns.columns]
        p_returns = returns[available_symbols].mul(w_series[available_symbols]).sum(axis=1)
        res = calculate_performance_metrics(p_returns)
        res["daily_returns"] = p_returns

        # Estimate turnover if initial_holdings provided
        if initial_holdings is not None:
            h_init = initial_holdings.reindex(w_series.index, fill_value=0.0)
            res["turnover"] = float((w_series - h_init).abs().sum()) / 2.0
        else:
            res["turnover"] = 0.0

        return res


class CVXPortfolioSimulator(BaseSimulator):
    """High-fidelity friction simulator using CVXPortfolio."""

    def __init__(self):
        try:
            import cvxportfolio as cvp

            self.cvp = cvp
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
        w_series = weights_df.set_index("Symbol")["Weight"].astype(float).reindex(universe, fill_value=0.0)
        non_cash_sum = float(w_series.drop(index=[cash_key]).abs().sum())
        w_series[cash_key] = max(0.0, 1.0 - non_cash_sum)
        w_series = w_series.fillna(0.0)
        policy = self.cvp.FixedWeights(w_series)
        cost_list: List[Any] = [self.cvp.TransactionCost(a=settings.backtest_slippage + settings.backtest_commission)]
        if settings.features.feat_short_costs:
            cost_list.append(self.cvp.HoldingCost(short_fees=settings.features.short_borrow_cost))
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
        try:
            # Dampening: Clip extreme returns to prevent solver failures
            returns_cvx = returns.astype(np.float64).clip(-0.5, 2.0)
            simulator = self.cvp.MarketSimulator(returns=returns_cvx, costs=cost_list, cash_key=cash_key, min_history=pd.Timedelta(days=0))
            result = simulator.backtest(policy, start_time=start_t, end_time=end_t, h=h_init)
            realized_returns = result.v.pct_change().dropna()
            res = calculate_performance_metrics(realized_returns)
            res.update({"daily_returns": realized_returns, "final_weights": result.w.iloc[-1], "turnover": float(result.turnover.sum()) / 2.0})
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
        w_series = weights_df.set_index("Symbol")["Weight"].astype(float)
        returns_vbt = returns.copy()
        for m in [s for s in w_series.index if s not in returns_vbt.columns]:
            returns_vbt[m] = 0.0
        portfolio = vbt.Portfolio.from_orders(
            close=returns_vbt[w_series.index] + 1.0,
            size=w_series,
            size_type="target_percent",
            fees=settings.backtest_slippage + settings.backtest_commission,
            freq="D",
        )
        p_returns = portfolio.returns()
        res = calculate_performance_metrics(p_returns)
        res["daily_returns"] = p_returns

        # Estimate turnover if initial_holdings provided
        if initial_holdings is not None:
            h_init = initial_holdings.reindex(w_series.index, fill_value=0.0)
            res["turnover"] = float((w_series - h_init).abs().sum()) / 2.0
        else:
            res["turnover"] = 0.0

        return res


def _sanitize_nt(symbol: str) -> str:
    """Sanitizes symbol for NautilusTrader (replaces non-alphanumeric with underscores)."""
    return re.sub(r"[^a-zA-Z0-9]", "_", symbol)


class NautilusSimulator(BaseSimulator):
    """Event-driven high-fidelity simulator using NautilusTrader (Placeholder)."""

    def simulate(self, returns: pd.DataFrame, weights_df: pd.DataFrame, initial_holdings: Optional[pd.Series] = None) -> Dict[str, Any]:
        return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)


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
