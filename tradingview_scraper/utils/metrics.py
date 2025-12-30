from __future__ import annotations

import logging
from typing import Any, Dict, Optional, cast

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Institutional Gates
MIN_OBSERVATIONS = 20
# Epsilon jitter to prevent empty slices in quantile-based risk metrics (returns < var)
EPSILON_JITTER = 1e-12


def _apply_jitter(rets: pd.Series) -> pd.Series:
    """Adds negligible unique noise to break ties in flat distributions (e.g. zero-filled weekends)."""
    if rets.empty:
        return rets
    return rets + np.linspace(0, EPSILON_JITTER, len(rets))


def _get_annualization_factor(rets: pd.Series) -> int:
    """Detects frequency and returns 252 for 5-day week or 365 for 7-day week."""
    try:
        # Check if weekends exist in the data
        idx = rets.index
        if not isinstance(idx, pd.DatetimeIndex):
            idx = pd.to_datetime(idx)

        # If Saturday or Sunday are present, use 365
        # Use getattr to bypass linter checks on DatetimeIndex
        days = getattr(idx, "dayofweek")
        if 5 in days or 6 in days:
            return 365
    except Exception:
        pass
    return 252


def calculate_performance_metrics(daily_returns: pd.Series) -> Dict[str, Any]:
    """
    Computes a standardized suite of performance metrics using QuantStats.
    Ensures mathematical consistency across all simulators and reports.
    """
    empty_res = {
        "total_return": 0.0,
        "annualized_return": 0.0,
        "realized_vol": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "var_95": None,
        "cvar_95": None,
        "sortino": 0.0,
        "calmar": 0.0,
        "omega": 0.0,
    }

    if daily_returns.empty:
        return empty_res

    # Clean returns
    rets = daily_returns.dropna()
    n_obs = len(rets)
    if n_obs == 0:
        return empty_res

    # 1. Basic Math (Always available)
    total_return = (1 + rets).prod() - 1
    ann_factor = _get_annualization_factor(rets)
    annualized_return = float(rets.mean() * ann_factor)

    vol_daily = rets.std()
    realized_vol = vol_daily * np.sqrt(ann_factor)

    cum_ret = (1 + rets).cumprod()
    running_max = cum_ret.cummax()
    drawdown = (cum_ret - running_max) / (running_max + 1e-12)
    max_drawdown = float(drawdown.min())

    # Gate for advanced/statistical metrics
    if n_obs < MIN_OBSERVATIONS:
        res = empty_res.copy()
        res.update(
            {
                "total_return": float(total_return),
                "annualized_return": float(annualized_return),
                "realized_vol": float(realized_vol),
                "max_drawdown": float(max_drawdown),
            }
        )
        return res

    try:
        import quantstats as qs

        # Use jittered returns for quantile-based stats to avoid empty slices/warnings
        rets_j = _apply_jitter(rets)

        # 2. Annualized Vol (QuantStats)
        realized_vol_qs = float(qs.stats.volatility(rets, periods=ann_factor))

        # 3. Sharpe Ratio (Annualized)
        sharpe = float(qs.stats.sharpe(rets, rf=0, periods=ann_factor))

        # 4. Drawdown
        max_drawdown_qs = float(qs.stats.max_drawdown(rets))

        # 5. Tail Risk (95% Confidence)
        var_95 = float(qs.stats.value_at_risk(rets_j, sigma=1, confidence=0.95))
        cvar_95 = float(qs.stats.expected_shortfall(rets_j, sigma=1, confidence=0.95))

        # 6. Advanced Stats
        sortino = float(qs.stats.sortino(rets, rf=0, periods=ann_factor))
        calmar = float(qs.stats.calmar(rets))
        omega = float(qs.stats.omega(rets))

        return {
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "realized_vol": float(realized_vol_qs),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown_qs),
            "var_95": float(var_95),
            "cvar_95": float(cvar_95),
            "sortino": sortino,
            "calmar": calmar,
            "omega": omega,
        }

    except Exception as e:
        logger.error(f"QuantStats calculation failed: {e}. Falling back to basic math.")
        sharpe = (rets.mean() * ann_factor) / (realized_vol + 1e-9)
        var_95_basic = float(rets.quantile(0.05))
        tail = rets[rets <= var_95_basic]
        cvar_95_basic = float(tail.mean()) if len(tail) > 0 else var_95_basic

        return {
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "realized_vol": float(realized_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "var_95": float(var_95_basic),
            "cvar_95": float(cvar_95_basic),
            "sortino": 0.0,
            "calmar": 0.0,
            "omega": 0.0,
        }


def get_metrics_markdown(daily_returns: pd.Series, benchmark: Optional[pd.Series] = None) -> str:
    """
    Returns a Markdown table of QuantStats metrics.
    """
    try:
        import quantstats as qs

        if len(daily_returns.dropna()) < MIN_OBSERVATIONS:
            return "Insufficient data for detailed metrics (minimum 20 days required)."

        # metrics returns a DataFrame with "Strategy" and optionally "Benchmark" columns
        # We use mode='full' for a comprehensive table
        df = qs.reports.metrics(daily_returns, benchmark=benchmark, display=False, mode="full")
        if df is None or df.empty:
            return "No metrics available."

        # Convert to Markdown
        return cast(str, df.to_markdown())
    except Exception as e:
        return f"Error generating metrics markdown: {e}"


def get_full_report_markdown(daily_returns: pd.Series, benchmark: Optional[pd.Series] = None, title: str = "Strategy", mode: str = "full") -> str:
    """
    Constructs a comprehensive Markdown report using QuantStats.
    Includes metrics, monthly returns, and drawdown audits.
    """
    try:
        import quantstats as qs

        # Clean series
        rets = daily_returns.dropna()
        n_obs = len(rets)

        # Align benchmark if provided
        if benchmark is not None:
            # Union of indices to handle different calendars (e.g. 24/7 Crypto vs 5/7 SPY)
            combined_idx = rets.index.union(benchmark.index)
            # Reindex and fill benchmark with 0.0 for missing days (market closed)
            # This ensures fair comparison during weekend crypto moves.
            benchmark = benchmark.reindex(combined_idx).fillna(0.0)
            rets = rets.reindex(combined_idx).fillna(0.0)

        md = []
        md.append(f"# Quantitative Strategy Tearsheet: {title}")
        md.append(f"Generated on: {pd.Timestamp.now()}\n")

        # 1. Key Metrics Table
        md.append("## 1. Key Performance Metrics")
        if n_obs >= MIN_OBSERVATIONS:
            metrics_df = qs.reports.metrics(rets, benchmark=benchmark, display=False, mode=mode)
            if metrics_df is not None and not metrics_df.empty:
                md.append(metrics_df.to_markdown())
        else:
            md.append(f"Insufficient data for detailed metrics ({n_obs} observations, 20 required).")
        md.append("")

        if mode == "full" and n_obs >= MIN_OBSERVATIONS:
            # 2. Monthly Returns Matrix
            md.append("## 2. Monthly Returns (%)")
            monthly = qs.stats.monthly_returns(rets)
            if monthly is not None and not monthly.empty:
                # Format as percentage for readability in table
                monthly_fmt = (monthly * 100).round(2)
                md.append(monthly_fmt.to_markdown())
            md.append("")

            # 3. Yearly Returns
            md.append("## 3. Annual Performance")
            if not rets.empty:
                # Reconstruct DatetimeIndex to ensure year access
                dti = pd.to_datetime(rets.index)
                # Use Any to bypass DatetimeIndex attribute check
                years = getattr(dti, "year")
                yearly = rets.groupby(years).apply(qs.stats.comp)
                if not yearly.empty:
                    yearly_fmt = pd.DataFrame((yearly * 100).round(2))
                    yearly_fmt.columns = ["Return (%)"]
                    md.append(yearly_fmt.to_markdown())
            md.append("")

            # 4. Worst Drawdowns
            md.append("## 4. Stress Audit: Worst 5 Drawdowns")
            dd_series = qs.stats.to_drawdown_series(rets)
            dd_details = qs.stats.drawdown_details(dd_series)
            if dd_details is not None and not dd_details.empty:
                # Search for a drawdown column to sort by
                cols = [str(c) for c in dd_details.columns if "drawdown" in str(c).lower()]
                if cols:
                    # Bypass type check for sort_values
                    sorted_df = getattr(dd_details, "sort_values")(by=cols[0], ascending=True)
                    md.append(cast(pd.DataFrame, sorted_df).head(5).to_markdown())
                else:
                    md.append(dd_details.head(5).to_markdown())
            md.append("")

        return "\n".join(md)

    except Exception as e:
        return f"# Strategy Report: {title}\n\nError generating full report: {e}"
