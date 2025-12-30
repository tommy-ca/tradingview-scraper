from __future__ import annotations

import logging
from typing import Any, Dict, Optional, cast

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


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
    if len(rets) == 0:
        return empty_res

    try:
        import quantstats as qs

        # 1. Basic Returns
        total_return = (1 + rets).prod() - 1

        # 2. Annualized Vol
        realized_vol = float(qs.stats.volatility(rets, annualize=True))

        # 3. Sharpe Ratio (Annualized)
        sharpe = float(qs.stats.sharpe(rets, rf=0))

        # 4. Drawdown
        max_drawdown = float(qs.stats.max_drawdown(rets))

        # 5. Tail Risk (95% Confidence)
        var_95 = float(qs.stats.value_at_risk(rets, sigma=1, confidence=0.95))
        cvar_95 = float(qs.stats.expected_shortfall(rets, sigma=1, confidence=0.95))

        # 6. Advanced Stats
        sortino = float(qs.stats.sortino(rets, rf=0))
        calmar = float(qs.stats.calmar(rets))
        omega = float(qs.stats.omega(rets))

        return {
            "total_return": float(total_return),
            "annualized_return": float(rets.mean() * 252),
            "realized_vol": float(realized_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "var_95": float(var_95),
            "cvar_95": float(cvar_95),
            "sortino": sortino,
            "calmar": calmar,
            "omega": omega,
        }

    except Exception as e:
        logger.error(f"QuantStats calculation failed: {e}. Falling back to basic math.")
        # Fallback to internal basic math if QuantStats fails or isn't installed
        total_return = (1 + rets).prod() - 1
        vol_daily = rets.std()
        realized_vol = vol_daily * np.sqrt(252)
        sharpe = (rets.mean() * 252) / (realized_vol + 1e-9)
        cum_ret = (1 + rets).cumprod()
        running_max = cum_ret.cummax()
        drawdown = (cum_ret - running_max) / (running_max + 1e-12)
        max_drawdown = float(drawdown.min())
        var_95 = float(rets.quantile(0.05))
        tail = rets[rets <= var_95]
        cvar_95 = float(tail.mean()) if len(tail) > 0 else var_95

        return {
            "total_return": float(total_return),
            "annualized_return": float(rets.mean() * 252),
            "realized_vol": float(realized_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "var_95": float(var_95),
            "cvar_95": float(cvar_95),
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

        # metrics returns a DataFrame with "Strategy" and optionally "Benchmark" columns
        # We use mode='full' for a comprehensive table
        df = qs.reports.metrics(daily_returns, benchmark=benchmark, display=False, mode="full")
        if df is None or df.empty:
            return "No metrics available."

        # Convert to Markdown
        return cast(str, df.to_markdown())
    except Exception as e:
        return f"Error generating metrics markdown: {e}"


def get_full_report_markdown(daily_returns: pd.Series, benchmark: Optional[pd.Series] = None, title: str = "Strategy") -> str:
    """
    Constructs a comprehensive Markdown report using QuantStats.
    Includes metrics, monthly returns, and drawdown audits.
    """
    try:
        import quantstats as qs

        # Align benchmark if provided
        if benchmark is not None:
            # Union of indices to handle different calendars (e.g. 24/7 Crypto vs 5/7 SPY)
            combined_idx = daily_returns.index.union(benchmark.index)
            # Reindex and fill benchmark with 0.0 for missing days (market closed)
            # This ensures fair comparison during weekend crypto moves.
            benchmark = benchmark.reindex(combined_idx).fillna(0.0)
            daily_returns = daily_returns.reindex(combined_idx).fillna(0.0)

        md = []
        md.append(f"# Quantitative Strategy Tearsheet: {title}")
        md.append(f"Generated on: {pd.Timestamp.now()}\n")

        # 1. Key Metrics Table
        md.append("## 1. Key Performance Metrics")
        metrics_df = qs.reports.metrics(daily_returns, benchmark=benchmark, display=False, mode="full")
        if metrics_df is not None and not metrics_df.empty:
            md.append(metrics_df.to_markdown())
        md.append("")

        # 2. Monthly Returns Matrix
        md.append("## 2. Monthly Returns (%)")
        monthly = qs.stats.monthly_returns(daily_returns)
        if monthly is not None and not monthly.empty:
            # Format as percentage for readability in table
            monthly_fmt = (monthly * 100).round(2)
            md.append(monthly_fmt.to_markdown())
        md.append("")

        # 3. Yearly Returns
        md.append("## 3. Annual Performance")
        if not daily_returns.empty:
            # Reconstruct DatetimeIndex to ensure year access
            dti = pd.to_datetime(daily_returns.index)
            # Use Any to bypass DatetimeIndex attribute check
            years = cast(Any, dti).year
            yearly = daily_returns.groupby(years).apply(qs.stats.comp)
            if not yearly.empty:
                yearly_fmt = pd.DataFrame((yearly * 100).round(2))
                yearly_fmt.columns = ["Return (%)"]
                md.append(yearly_fmt.to_markdown())
        md.append("")

        # 4. Worst Drawdowns
        md.append("## 4. Stress Audit: Worst 5 Drawdowns")
        dd_series = qs.stats.to_drawdown_series(daily_returns)
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
