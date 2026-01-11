from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ClusteredUniverse:
    returns: pd.DataFrame
    clusters: Dict[str, List[str]]
    cluster_benchmarks: pd.DataFrame
    intra_cluster_weights: Dict[str, pd.Series]
    cluster_stats: Dict[str, Dict[str, float]]
    symbol_to_cluster: Dict[str, str]


def _norm(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    if len(series) == 1:
        return pd.Series(1.0, index=series.index)
    return (series - series.min()) / (series.max() - series.min() + 1e-9)


def build_clustered_universe(
    *,
    returns: pd.DataFrame,
    clusters: Dict[str, List[str]],
    meta: Optional[Dict[str, Any]] = None,
    stats: Optional[pd.DataFrame] = None,
) -> ClusteredUniverse:
    """Builds cluster benchmarks and intra-cluster weights.

    This mirrors the initialization logic in `scripts/optimize_clustered_v2.py`,
    but works from in-memory DataFrames for use in backtests/tournaments.
    """

    meta = meta or {}

    # Ensure returns matches clusters
    all_symbols = [s for c in clusters.values() for s in c]
    available_symbols = [s for s in all_symbols if s in returns.columns]
    aligned_returns = cast(pd.DataFrame, returns[available_symbols].dropna(how="any"))

    cluster_benchmarks = pd.DataFrame(index=aligned_returns.index)
    intra_cluster_weights: Dict[str, pd.Series] = {}
    cluster_stats: Dict[str, Dict[str, float]] = {}
    symbol_to_cluster: Dict[str, str] = {}

    for c_id, symbols in clusters.items():
        for s in symbols:
            symbol_to_cluster[str(s)] = str(c_id)

        valid_symbols = [s for s in symbols if s in aligned_returns.columns]
        if not valid_symbols:
            continue

        sub_rets = aligned_returns[valid_symbols]

        mom = cast(pd.Series, sub_rets.mean() * 252)
        # Handle cases where sub_rets has insufficient data for std()
        vols = pd.Series(0.0, index=valid_symbols)
        for s in valid_symbols:
            s_rets = sub_rets[s].dropna()
            if len(s_rets) > 1:
                vols[s] = float(s_rets.std() * np.sqrt(252))
            else:
                vols[s] = 0.0
        stab = cast(pd.Series, 1.0 / (vols + 1e-9))

        conv = pd.Series(0.0, index=valid_symbols)
        if stats is not None and not stats.empty and "Symbol" in stats.columns:
            common = [s for s in valid_symbols if s in stats["Symbol"].values]
            if common and "Antifragility_Score" in stats.columns:
                conv.loc[common] = stats.set_index("Symbol").loc[common, "Antifragility_Score"]

        liq = pd.Series(0.0, index=valid_symbols)
        for s in valid_symbols:
            m = meta.get(str(s), {}) if isinstance(meta, dict) else {}
            vt = float(m.get("value_traded", 0) or 0)
            atr = float(m.get("atr", 0) or 0)
            price = float(m.get("close", 0) or 0)

            spread_proxy = 0.0
            if atr > 0 and price > 0:
                spread_pct = atr / price
                spread_pct = max(spread_pct, 1e-6)
                spread_proxy = 1.0 / spread_pct
                spread_proxy = min(spread_proxy, 1e6)

            liq[s] = 0.7 * np.log1p(max(vt, 0.0)) + 0.3 * np.log1p(spread_proxy)

        # 1. HERC 2.0: Intra-Cluster Risk Parity
        # We assign weights based on inverse variance to ensure equal risk
        # contribution within each cluster bucket.
        inv_vars = 1.0 / (vols**2 + 1e-12)
        w_ivp = inv_vars / inv_vars.sum()

        # Intra-cluster weights are now purely risk-based
        w_intra = w_ivp

        # 2. Cluster Benchmark Calculation
        # The benchmark return for this cluster is the risk-weighted average of its assets.
        bench_rets = cast(pd.Series, (sub_rets * w_intra).sum(axis=1))
        # Standard check with length guard
        if len(bench_rets.dropna()) > 1 and bench_rets.std() > 1e-12:
            cluster_benchmarks[f"Cluster_{c_id}"] = bench_rets
            intra_cluster_weights[str(c_id)] = w_intra
        else:
            # Skip zero-variance cluster
            continue

        # Aggregate cluster fragility (CVaR) and structural metrics
        if stats is not None and not stats.empty and "Symbol" not in stats.columns:
            # Fallback stats logic
            pass

        # Use the actual detector to get structural metrics for the cluster benchmark
        from tradingview_scraper.regime import MarketRegimeDetector

        detector = MarketRegimeDetector()
        c_hurst = detector._hurst_exponent(bench_rets.values)

        if stats is not None and not stats.empty and "Symbol" in stats.columns:
            c_af_stats = stats[stats["Symbol"].isin(valid_symbols)]
            if not c_af_stats.empty:
                if "Fragility_Score" in c_af_stats.columns:
                    fragility = float(np.mean(c_af_stats["Fragility_Score"]))
                else:
                    if "Antifragility_Score" in c_af_stats.columns:
                        antif = c_af_stats["Antifragility_Score"]
                        anti_norm = antif / (float(antif.max()) + 1e-9)
                    else:
                        anti_norm = pd.Series(0.0, index=c_af_stats.index)

                    if "CVaR_95" in c_af_stats.columns:
                        tail = np.abs(c_af_stats["CVaR_95"])
                    elif "Vol" in c_af_stats.columns:
                        tail = c_af_stats["Vol"]
                    else:
                        tail = pd.Series(0.0, index=c_af_stats.index)

                    tail_norm = tail / (float(np.max(tail)) + 1e-9) if len(tail) else tail
                    fragility = float(np.mean((1.0 - anti_norm) + tail_norm))

                if "CVaR_95" in c_af_stats.columns:
                    cvar_value = float(np.mean(c_af_stats["CVaR_95"]))
                elif "Vol" in c_af_stats.columns:
                    cvar_value = float(np.mean(c_af_stats["Vol"]))
                else:
                    cvar_value = -0.05

                cluster_stats[str(c_id)] = {"fragility": fragility, "cvar": cvar_value, "hurst": c_hurst}
            else:
                cluster_stats[str(c_id)] = {"fragility": 1.0, "cvar": -0.05, "hurst": c_hurst}
        else:
            cluster_stats[str(c_id)] = {"fragility": 1.0, "cvar": -0.05, "hurst": c_hurst}

    return ClusteredUniverse(
        returns=aligned_returns,
        clusters=clusters,
        cluster_benchmarks=cluster_benchmarks,
        intra_cluster_weights=intra_cluster_weights,
        cluster_stats=cluster_stats,
        symbol_to_cluster=symbol_to_cluster,
    )
