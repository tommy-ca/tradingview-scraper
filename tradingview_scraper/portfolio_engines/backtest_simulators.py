import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, cast

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
        target_len = len(returns)

        w_target = weights_df.set_index("Symbol")["Weight"].astype(float)
        if isinstance(w_target, pd.DataFrame):
            w_target = w_target.iloc[:, 0]
        w_target = cast(pd.Series, w_target)
        if "cash" not in w_target.index:
            w_target["cash"] = max(0.0, 1.0 - w_target.sum())

        rebalance_mode = settings.features.feat_rebalance_mode
        tolerance_enabled = settings.features.feat_rebalance_tolerance
        drift_limit = settings.features.rebalance_drift_limit
        total_rate = settings.backtest_slippage + settings.backtest_commission

        # 1. Initial Rebalance at t=0
        turnover_t0 = _calculate_standard_turnover(w_target, initial_holdings)
        friction_t0 = turnover_t0 * 2.0 * total_rate

        daily_p_rets = []
        current_weights = w_target.copy()
        total_turnover = turnover_t0

        for t in range(target_len):
            returns_t = returns.iloc[t].reindex(current_weights.index, fill_value=0.0)

            p_ret_t = (current_weights * returns_t).sum()

            drift_weights = current_weights * (1 + returns_t)
            drift_weights = drift_weights / drift_weights.sum()

            friction_t = 0.0

            if rebalance_mode == "daily":
                do_rebalance = True
                if tolerance_enabled:
                    drift_dist = (drift_weights - w_target).abs().sum() / 2.0
                    if drift_dist <= drift_limit:
                        do_rebalance = False

                if do_rebalance:
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

        p_returns = pd.Series(daily_p_rets, index=returns.index)
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
            self.cvp = None
            self.Policy = None

    def simulate(
        self,
        returns: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        if self.cvp is None:
            return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)

        settings = get_settings()
        cash_key = "cash"

        start_t = returns.index[0]
        end_t = returns.index[-1]
        universe = list(returns.columns)
        if cash_key not in universe:
            universe.append(cash_key)

        w_target_raw = weights_df.set_index("Symbol")["Weight"].astype(float)
        if isinstance(w_target_raw, pd.DataFrame):
            w_target_raw = w_target_raw.iloc[:, 0]
        w_target = cast(pd.Series, w_target_raw).reindex(universe, fill_value=0.0)

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
            returns_cvx = returns.astype(np.float64).clip(-0.5, 2.0).fillna(0.0)

            # Explicitly add cash if not present to avoid CVXPortfolio auto-injection warnings and alignment issues
            if cash_key not in returns_cvx.columns:
                returns_cvx[cash_key] = 0.0

            simulator = self.cvp.MarketSimulator(returns=returns_cvx, costs=cost_list, cash_key=cash_key, min_history=pd.Timedelta(days=0))

            # Ensure holdings and universe are perfectly aligned for the simulator
            h_init_cvx = h_init.reindex(returns_cvx.columns, fill_value=0.0)

            result = simulator.backtest(policy, start_time=start_t, end_time=end_t, h=h_init_cvx)

            realized_returns = result.v.pct_change().dropna()
            realized_returns.index = returns.index[: len(realized_returns)]

            res = calculate_performance_metrics(realized_returns)
            res.update({"daily_returns": realized_returns, "final_weights": result.w.iloc[-1], "turnover": float(result.turnover.sum())})
            return res
        except Exception as e:
            logger.error(f"cvxportfolio failed: {e}")
            return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)


# Backward-compatible alias (legacy/tests).
CvxPortfolioSimulator = CVXPortfolioSimulator


class VectorBTSimulator(BaseSimulator):
    """High-performance vectorized simulator using VectorBT."""

    def __init__(self):
        try:
            import vectorbt as vbt

            self.vbt = vbt
        except ImportError:
            self.vbt = None

    def simulate(
        self,
        returns: pd.DataFrame,
        weights_df: pd.DataFrame,
        initial_holdings: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        if self.vbt is None:
            return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)

        vbt = self.vbt
        settings = get_settings()

        rebalance_mode = settings.features.feat_rebalance_mode
        w_series = weights_df.set_index("Symbol")["Weight"].astype(float)
        if isinstance(w_series, pd.DataFrame):
            w_series = w_series.iloc[:, 0]
        w_series = cast(pd.Series, w_series)

        prices = (1.0 + returns[w_series.index]).cumprod()

        if rebalance_mode == "daily":
            w_df = pd.DataFrame([w_series.values] * len(prices), columns=w_series.index, index=prices.index)
        else:
            w_df = pd.DataFrame(np.nan, columns=w_series.index, index=prices.index)
            w_df.iloc[0] = w_series.values

        portfolio = vbt.Portfolio.from_orders(
            close=prices, size=w_df, size_type="target_percent", fees=settings.backtest_slippage + settings.backtest_commission, freq="D", init_cash=100.0, cash_sharing=True, group_by=True
        )
        # Shift and cap returns
        p_returns = portfolio.returns().fillna(0.0)

        res = calculate_performance_metrics(p_returns)
        res["daily_returns"] = p_returns

        # Calculate true turnover from trades
        # value() gives total portfolio value.
        # trades.value() gives value of each trade.
        # Sum of absolute trade values / 2 = Turnover
        # But we need to be careful about initial vs drift

        # NOTE: VBT trades might include the initial buy-in.
        # If we passed initial_holdings, VBT doesn't know about them in `from_orders` unless we start with positions?
        # `from_orders` assumes cash start.
        # So VBT simulation here IS from cash.
        # Turnover reported by VBT trades will be sum(|trades|)/2
        # But this includes the full buy-in turnover (1.0).
        # We need to replace the t0 turnover with the delta from initial_holdings.

        # Get total VBT turnover
        # trades.value is a Series.
        # But wait, group_by=True means we have one group.
        # portfolio.trades.value() returns a Series of trade values.
        # We sum abs.

        # Better: use our calculated turnover for t0, and add VBT turnover for t1+?
        # In window mode, no trades after t0. So _calculate_standard_turnover is correct.
        # In daily mode, trades happen t1+.

        t0_turnover = _calculate_standard_turnover(w_series, initial_holdings)

        if rebalance_mode == "daily":
            # VBT Total turnover = t0_full_buy + t1_drift + ...
            # We want = t0_delta + t1_drift + ...
            # So we take VBT Total - t0_full_buy + t0_delta

            # Estimate VBT t0 turnover (should be ~1.0 if full invested)
            vbt_t0_turnover = _calculate_standard_turnover(w_series, None)

            # Approximate total turnover from VBT stats?
            # Or assume drift is small and our t0 turnover is dominant?
            # Let's try to get VBT total trade value.
            try:
                # Value of all trades
                total_trade_val = portfolio.trades().value.abs().sum()
                vbt_total_turnover = total_trade_val / 2.0 / 100.0  # Normalize by init_cash=100

                # Correct it
                final_turnover = vbt_total_turnover - vbt_t0_turnover + t0_turnover
                res["turnover"] = max(0.0, final_turnover)
            except Exception:
                # Fallback
                res["turnover"] = t0_turnover
        else:
            res["turnover"] = t0_turnover

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
        try:
            from tradingview_scraper.portfolio_engines.nautilus_adapter import run_nautilus_backtest

            return run_nautilus_backtest(returns=returns, weights_df=weights_df, initial_holdings=initial_holdings, settings=get_settings())
        except Exception as e:
            logger.warning(f"Nautilus adapter unavailable, falling back to custom simulator: {e}")
            return ReturnsSimulator().simulate(returns, weights_df, initial_holdings)
