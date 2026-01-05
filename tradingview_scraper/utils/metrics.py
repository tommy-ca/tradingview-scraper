from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, cast

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

    # Consistent Timezone Handling - Force Naive
    rets = daily_returns.dropna().copy()
    try:
        new_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in rets.index]
        rets.index = pd.DatetimeIndex(new_idx)
    except Exception as e_idx:
        logger.debug(f"Metrics index forcing failed: {e_idx}")
        if rets.index.tz is not None:
            rets.index = rets.index.tz_convert(None).tz_localize(None)
        else:
            rets.index = rets.index.tz_localize(None)

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
        # Avoid division-by-zero RuntimeWarning inside QuantStats when max drawdown is 0.
        calmar = float(annualized_return) / (abs(max_drawdown_qs) + 1e-12)
        omega = float(qs.stats.omega(rets))

        return {
            "total_return": float(total_return),
            "annualized_return": float(annualized_return),
            "realized_vol": float(realized_vol_qs),
            "annualized_vol": float(realized_vol_qs),
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
            "annualized_vol": float(realized_vol),
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

        rets = daily_returns.dropna().copy()

        # Consistent Timezone Handling - Force Naive
        try:
            new_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in rets.index]
            rets.index = pd.DatetimeIndex(new_idx)
        except Exception:
            if rets.index.tz is not None:
                rets.index = rets.index.tz_convert(None).tz_localize(None)
            else:
                rets.index = rets.index.tz_localize(None)

        if benchmark is not None:
            benchmark = benchmark.copy()
            try:
                new_b_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in benchmark.index]
                benchmark.index = pd.DatetimeIndex(new_b_idx)
            except Exception:
                if benchmark.index.tz is not None:
                    benchmark.index = benchmark.index.tz_convert(None).tz_localize(None)
                else:
                    benchmark.index = benchmark.index.tz_localize(None)

            idx = rets.index.union(benchmark.index)
            benchmark = benchmark.reindex(idx).fillna(0.0)
            rets = rets.reindex(idx).fillna(0.0)

        n_obs = len(rets)

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


def calculate_temporal_fragility(sharpe_series: pd.Series) -> float:
    """Coefficient of variation of Sharpe across windows."""
    s = sharpe_series.dropna()
    if s.empty or len(s) < 2:
        return 0.0
    mean_sharpe = float(s.mean())
    if abs(mean_sharpe) < 1e-9:
        return 0.0
    return float(s.std() / abs(mean_sharpe))


def calculate_friction_alignment(sharpe_real: float, sharpe_ideal: float) -> float:
    """Sharpe decay ratio from idealized -> high-fidelity simulation."""
    if abs(sharpe_ideal) < 1e-9:
        return 0.0
    return float(1.0 - (sharpe_real / sharpe_ideal))


def calculate_selection_jaccard(universe_a: List[str], universe_b: List[str]) -> float:
    """Jaccard similarity between two symbol sets."""
    set_a = set(universe_a)
    set_b = set(universe_b)
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    if union == 0:
        return 1.0
    return float(intersection / union)


def calculate_antifragility_distribution(
    daily_returns: pd.Series,
    *,
    q: float = 0.95,
    min_obs: int = 100,
    min_tail: int = 10,
    eps: float = 1e-12,
) -> Dict[str, Any]:
    """Quantified antifragility from return distribution (skew + tail asymmetry)."""
    rets = daily_returns.dropna().copy()
    n_obs = int(len(rets))
    if n_obs < min_obs:
        return {"n_obs": n_obs, "is_sufficient": False}

    # Use negligible jitter to avoid tie-driven empty tails, then select tails on
    # the jittered thresholds but compute statistics on the original returns.
    rets_j = _apply_jitter(rets)

    q_hi = float(rets_j.quantile(q))
    q_lo = float(rets_j.quantile(1.0 - q))

    right_tail = rets[rets_j >= q_hi]
    left_tail = rets[rets_j <= q_lo]

    n_right = int(len(right_tail))
    n_left = int(len(left_tail))

    # Tail sufficiency should be coherent with the chosen quantile and the sample size.
    # Example: at q=0.95 with 160 observations, the expected tail size is ~8; requiring
    # 10 tail points would make the metric permanently unavailable for small smokes.
    expected_tail = max(1, int(math.floor((1.0 - float(q)) * float(n_obs))))
    min_tail_eff = min(int(min_tail), expected_tail)
    if n_right < min_tail_eff or n_left < min_tail_eff:
        return {
            "q": float(q),
            "n_obs": n_obs,
            "n_right": n_right,
            "n_left": n_left,
            "min_tail_required": int(min_tail_eff),
            "is_sufficient": False,
        }

    skew = float(rets.skew())
    tail_gain = float(right_tail.mean())
    tail_loss = float(abs(left_tail.mean()))

    if tail_gain <= 0:
        tail_asym = 0.0
    else:
        tail_asym = float(tail_gain / (tail_loss + eps))

    af_dist = float(skew + math.log(tail_asym + eps))

    return {
        "q": float(q),
        "n_obs": n_obs,
        "n_right": n_right,
        "n_left": n_left,
        "min_tail_required": int(min_tail_eff),
        "skew": skew,
        "tail_gain": tail_gain,
        "tail_loss": tail_loss,
        "tail_asym": tail_asym,
        "af_dist": af_dist,
        "is_sufficient": True,
    }


def calculate_antifragility_stress(
    strategy_returns: pd.Series,
    reference_returns: pd.Series,
    *,
    q_stress: float = 0.10,
    min_obs: int = 100,
    min_stress: int = 10,
) -> Dict[str, Any]:
    """Quantified antifragility from stress response vs a reference baseline."""
    strat = strategy_returns.dropna().copy()
    ref = reference_returns.dropna().copy()

    idx = strat.index.intersection(ref.index)
    if idx.empty:
        return {"n_obs": 0, "is_sufficient": False}

    strat = strat.reindex(idx)
    ref = ref.reindex(idx)

    n_obs = int(len(idx))
    if n_obs < min_obs:
        return {"n_obs": n_obs, "is_sufficient": False}

    stress_cut = float(ref.quantile(q_stress))
    stress_mask = ref <= stress_cut
    n_stress = int(stress_mask.sum())
    if n_stress < min_stress:
        return {"q_stress": float(q_stress), "n_obs": n_obs, "n_stress": n_stress, "is_sufficient": False}

    diff = strat - ref

    stress_alpha = float(diff[stress_mask].mean())
    calm_alpha = float(diff[~stress_mask].mean())
    stress_delta = float(stress_alpha - calm_alpha)

    stress_mean = float(strat[stress_mask].mean())
    calm_mean = float(strat[~stress_mask].mean())

    stress_hit_rate = float((strat[stress_mask] > ref[stress_mask]).mean())

    return {
        "q_stress": float(q_stress),
        "n_obs": n_obs,
        "n_stress": n_stress,
        "stress_alpha": stress_alpha,
        "calm_alpha": calm_alpha,
        "stress_delta": stress_delta,
        "stress_mean": stress_mean,
        "calm_mean": calm_mean,
        "stress_hit_rate": stress_hit_rate,
        "is_sufficient": True,
    }
