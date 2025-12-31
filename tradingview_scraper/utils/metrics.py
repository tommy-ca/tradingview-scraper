from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional, cast

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Institutional Gates
# Lowered significantly to allow metrics for short walk-forward windows (e.g. 20d)
MIN_OBSERVATIONS = 5
# Epsilon jitter to prevent empty slices in quantile-based risk metrics (returns < var)
EPSILON_JITTER = 1e-12


def _apply_jitter(rets: pd.Series) -> pd.Series:
    """Adds negligible unique noise to break ties in flat distributions."""
    if rets.empty:
        return rets
    return rets + np.linspace(0, EPSILON_JITTER, len(rets))


def _get_annualization_factor(rets: pd.Series) -> int:
    """Detects frequency and returns 252 for 5-day week or 365 for 7-day week."""
    try:
        idx = rets.index
        if not isinstance(idx, pd.DatetimeIndex):
            idx = pd.to_datetime(idx)
        days = getattr(idx, "dayofweek")
        if any(d in [5, 6] for d in days):
            return 365
    except Exception:
        pass
    return 252


def calculate_performance_metrics(daily_returns: pd.Series) -> Dict[str, Any]:
    """
    Computes a standardized suite of performance metrics using QuantStats.
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
    rets = daily_returns.dropna()
    n_obs = len(rets)
    if n_obs == 0:
        return empty_res

    total_return = (1 + rets).prod() - 1
    ann_factor = _get_annualization_factor(rets)
    annualized_return = float(rets.mean() * ann_factor)

    vol_daily = rets.std()
    realized_vol = vol_daily * math.sqrt(ann_factor)

    cum_ret = (1 + rets).cumprod()
    running_max = cum_ret.cummax()
    drawdown = (cum_ret - running_max) / (running_max + 1e-12)
    max_drawdown = float(drawdown.min())

    if n_obs < MIN_OBSERVATIONS:
        res = empty_res.copy()
        res.update({"total_return": float(total_return), "annualized_return": float(annualized_return), "realized_vol": float(realized_vol), "max_drawdown": float(max_drawdown)})
        return res

    try:
        import quantstats as qs

        rets_j = _apply_jitter(rets)

        # QuantStats metrics
        realized_vol_qs = float(qs.stats.volatility(rets, periods=ann_factor))
        sharpe = float(qs.stats.sharpe(rets, rf=0, periods=ann_factor))
        max_drawdown_qs = float(qs.stats.max_drawdown(rets))
        var_95 = float(qs.stats.value_at_risk(rets_j, sigma=1, confidence=0.95))

        # Guard for CVaR calculation to avoid Mean of empty slice warning
        try:
            if any(rets_j < var_95):
                cvar_95 = float(qs.stats.expected_shortfall(rets_j, sigma=1, confidence=0.95))
            else:
                cvar_95 = var_95
        except Exception:
            cvar_95 = var_95

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
        logger.debug(f"QuantStats failed: {e}")
        sharpe = (rets.mean() * ann_factor) / (realized_vol + 1e-9)
        return {
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "realized_vol": float(realized_vol),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_drawdown),
            "var_95": float(rets.quantile(0.05)),
            "cvar_95": float(rets[rets <= rets.quantile(0.05)].mean() if len(rets[rets <= rets.quantile(0.05)]) > 0 else rets.quantile(0.05)),
            "sortino": 0.0,
            "calmar": 0.0,
            "omega": 0.0,
        }


def get_metrics_markdown(daily_returns: pd.Series, benchmark: Optional[pd.Series] = None) -> str:
    try:
        import quantstats as qs

        if len(daily_returns.dropna()) < MIN_OBSERVATIONS:
            return f"Insufficient data ({len(daily_returns.dropna())} obs)."
        df = qs.reports.metrics(daily_returns, benchmark=benchmark, display=False, mode="full")
        return cast(str, df.to_markdown()) if df is not None else "No metrics."
    except Exception as e:
        return f"Error: {e}"


def get_full_report_markdown(daily_returns: pd.Series, benchmark: Optional[pd.Series] = None, title: str = "Strategy", mode: str = "full") -> str:
    try:
        import quantstats as qs

        rets = daily_returns.dropna()
        n_obs = len(rets)
        if benchmark is not None:
            idx = rets.index.union(benchmark.index)
            benchmark = benchmark.reindex(idx).fillna(0.0)
            rets = rets.reindex(idx).fillna(0.0)

        md = [f"# Quantitative Strategy Tearsheet: {title}", f"Generated on: {pd.Timestamp.now()}\n"]
        md.append("## 1. Key Performance Metrics")
        if n_obs >= MIN_OBSERVATIONS:
            m_df = qs.reports.metrics(rets, benchmark=benchmark, display=False, mode=mode)
            if m_df is not None:
                m_md = m_df.to_markdown()
                if m_md:
                    md.append(cast(str, m_md))
        else:
            md.append(f"Insufficient data ({n_obs} observations).")

        if mode == "full" and n_obs >= MIN_OBSERVATIONS:
            md.append("\n## 2. Monthly Returns (%)")
            monthly = qs.stats.monthly_returns(rets)
            if monthly is not None:
                mon_md = (monthly * 100).round(2).to_markdown()
                if mon_md:
                    md.append(cast(str, mon_md))

            md.append("\n## 3. Annual Performance")
            dti = pd.to_datetime(rets.index)
            yearly = rets.groupby(getattr(dti, "year")).apply(qs.stats.comp)
            if not yearly.empty:
                yearly_df = pd.DataFrame({"Return (%)": (yearly * 100).round(2)})
                yearly_md = yearly_df.to_markdown()
                if yearly_md:
                    md.append(cast(str, yearly_md))

            md.append("\n## 4. Stress Audit: Worst 5 Drawdowns")
            dd_details = qs.stats.drawdown_details(qs.stats.to_drawdown_series(rets))
            if dd_details is not None and not dd_details.empty:
                cols = [str(c) for c in dd_details.columns if "drawdown" in str(c).lower()]
                if cols:
                    dd_df = cast(pd.DataFrame, dd_details)
                    dd_sorted = dd_df.sort_values(by=[cols[0]], ascending=True)
                    dd_md = dd_sorted.head(5).to_markdown()

                    if dd_md:
                        md.append(cast(str, dd_md))

        return "\n".join(md)
    except Exception as e:
        return f"# Strategy Report: {title}\n\nError: {e}"
