from __future__ import annotations
import dataclasses
import logging
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import ledoit_wolf

from tradingview_scraper.portfolio_engines.base import (
    BaseRiskEngine, EngineRequest, EngineResponse, ProfileName,
    _effective_cap, _safe_series, _enforce_cap_series
)
from tradingview_scraper.portfolio_engines.cluster_adapter import ClusteredUniverse, build_clustered_universe
from tradingview_scraper.settings import get_settings

logger = logging.getLogger(__name__)

def _get_recursive_bisection_weights(cov: np.ndarray, sort_ix: List[int]) -> np.ndarray:
    weights = np.ones(len(sort_ix)); items = [sort_ix]
    while len(items) > 0:
        items = [i[j:k] for i in items for j, k in ((0, len(i) // 2), (len(i) // 2, len(i))) if len(i) > 1]
        for i in range(0, len(items), 2):
            l, r = items[i], items[i + 1]
            v_l, v_r = np.trace(cov[l][:, l]), np.trace(cov[r][:, r])
            alpha = 1 - v_l / (v_l + v_r + 1e-15)
            weights[l] *= alpha; weights[r] *= 1 - alpha
    return weights

def _weights_df_from_cluster_weights(*, universe: ClusteredUniverse, cluster_weights: pd.Series, meta: Optional[Dict[str, Any]], scale: float = 1.0) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []; meta = meta or {}
    for col, c_w in cluster_weights.items():
        c_w_scalar = float(c_w)
        if c_w_scalar <= 0: continue
        intra = universe.intra_cluster_weights.get(str(col).replace("Cluster_", ""))
        if intra is None or intra.empty: continue
        for sym, sym_w in intra.items():
            sym_w_scalar = float(sym_w)
            w = c_w_scalar * sym_w_scalar * scale
            if w <= 1e-9: continue
            m = meta.get(str(sym), {}); d = str(m.get("direction", "LONG"))
            rows.append({"Symbol": str(sym), "Weight": float(w), "Net_Weight": float(w) * (1.0 if d == "LONG" else -1.0), "Direction": d, "Cluster_ID": str(col).replace("Cluster_", ""), "Cluster_Weight": c_w_scalar * scale, "Intra_Cluster_Weight": sym_w_scalar, "Type": "CORE", "Description": m.get("description", "N/A"), "Sector": m.get("sector", "N/A"), "Market": m.get("market", "UNKNOWN")})
    if not rows: return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"]))
    df = pd.DataFrame(rows).sort_values("Weight", ascending=False); total = float(df["Weight"].sum())
    if total > 0: factor = scale / (total + 1e-12); df["Weight"] *= factor; df["Net_Weight"] *= factor
    return df

def _cov_shrunk(returns: pd.DataFrame, kappa_thresh: float = 15000.0, default_shrinkage: float = 0.01) -> np.ndarray:
    if returns.shape[1] < 2: 
        c = returns.cov().values * 252
        return np.asarray(c, dtype=float)
    s_cov, _ = ledoit_wolf(returns.values); cov = s_cov * 252
    n, shr = cov.shape[0], default_shrinkage
    while shr <= 0.1:
        vols = np.sqrt(np.diag(cov) + 1e-15); corr = cov / np.outer(vols, vols)
        corr_r = corr * (1.0 - shr) + np.eye(n) * shr
        evs = np.linalg.eigvalsh(corr_r); k = float(evs.max() / (np.abs(evs).min() + 1e-15))
        if k <= kappa_thresh: return np.outer(vols, vols) * corr_r
        shr += 0.01
    return cov + np.eye(n) * 0.1 * np.mean(np.diag(cov))

def _solve_cvxpy(*, n, cap, cov, mu=None, penalties=None, profile="min_variance", risk_free_rate=0.0, prev_weights=None, l2_gamma=0.0, solver=None, solver_options=None):
    import cvxpy as cp
    import importlib.util
    if n <= 0: return np.array([]); 
    if n == 1: return np.array([1.0])
    w = cp.Variable(n); constraints = [cp.sum(w) == 1.0, w >= 0.0, w <= cap]
    risk = cp.quad_form(w, cov + np.eye(n) * 1e-6)
    p_t = (w @ penalties) * 0.2 if penalties is not None else 0.0
    l2 = float(l2_gamma) * cp.sum_squares(w) if float(l2_gamma) > 0 else 0.0
    t_p = 0.0; settings_obj = get_settings()
    if settings_obj.features.feat_turnover_penalty and prev_weights is not None and prev_weights.size == n: 
        t_p = cp.norm(w - prev_weights, 1) * 0.001
    if profile == "min_variance": obj = cp.Minimize(risk + p_t + t_p + l2)
    elif profile == "risk_parity" or profile == "erc": obj = cp.Minimize(0.5 * risk - (1.0 / n) * cp.sum(cp.log(w)) + t_p + l2)
    elif profile == "max_sharpe":
        mu_vec = np.asarray(mu if mu is not None else np.zeros(n), dtype=float).flatten()
        obj = cp.Maximize((mu_vec @ w) - 0.5 * risk - p_t - t_p - l2)
    else: obj = cp.Minimize(risk + t_p + l2)
    try:
        prob = cp.Problem(obj, constraints); active_s = getattr(cp, solver.upper(), None) if solver else (cp.CLARABEL if importlib.util.find_spec("clarabel") else (cp.ECOS if profile in ["risk_parity", "erc"] else cp.OSQP))
        options = solver_options or {}; prob.solve(solver=active_s, **options)
        if w.value is None or prob.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}: return np.array([1.0 / n] * n)
        return np.array(w.value).flatten()
    except Exception: return np.array([1.0 / n] * n)

def _cluster_penalties(u): return np.array([float(u.cluster_stats.get(str(c).replace("Cluster_", ""), {}).get("fragility", 1.0)) for c in u.cluster_benchmarks.columns])

class CustomClusteredEngine(BaseRiskEngine):
    @property
    def name(self) -> str: return "custom"
    @classmethod
    def is_available(cls) -> bool: return True
    
    def optimize(self, *, returns, clusters, meta, stats, request):
        s = get_settings()
        if request.profile == "market":
            targets = [sym for sym in s.benchmark_symbols if sym in returns.columns]
            if not targets: return EngineResponse(self.name, request, pd.DataFrame(), {"backend": "market_empty"}, ["benchmark missing"])
            w = 1.0 / len(targets); rows = [{"Symbol": str(t), "Weight": w, "Net_Weight": w * (1.0 if (meta or {}).get(str(t), {}).get("direction", "LONG") == "LONG" else -1.0), "Direction": (meta or {}).get(str(t), {}).get("direction", "LONG"), "Cluster_ID": "MARKET", "Description": (meta or {}).get(str(t), {}).get("description", "N/A")} for t in targets]
            return EngineResponse(self.name, request, pd.DataFrame(rows), {"backend": "market_static"}, [])
        if request.profile == "benchmark":
            targets = list(returns.columns)
            if not targets: return EngineResponse(self.name, request, pd.DataFrame(), {"backend": "benchmark_empty"}, ["empty returns"])
            w = 1.0 / len(targets); rows = [{"Symbol": str(t), "Weight": w, "Net_Weight": w * (1.0 if (meta or {}).get(str(t), {}).get("direction", "LONG") == "LONG" else -1.0), "Direction": (meta or {}).get(str(t), {}).get("direction", "LONG"), "Cluster_ID": "BENCHMARK", "Description": (meta or {}).get(str(t), {}).get("description", "N/A")} for t in targets]
            return EngineResponse(self.name, request, pd.DataFrame(rows), {"backend": "benchmark_ew"}, [])
        
        u = build_clustered_universe(returns=returns, clusters=clusters, meta=meta, stats=stats)
        if u.cluster_benchmarks.empty: return EngineResponse(self.name, request, pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["empty universe"])
        
        if request.profile == "barbell":
            w_df, m_out, warn = self._barbell(universe=u, meta=meta, stats=stats, request=request)
            return EngineResponse(self.name, request, w_df, m_out, warn)
        
        c_w = self._optimize_cluster_weights(universe=u, request=request)
        return EngineResponse(self.name, request, _weights_df_from_cluster_weights(universe=u, cluster_weights=c_w, meta=meta), {"backend": "custom"}, [])

    def _optimize_cluster_weights(self, *, universe, request) -> pd.Series:
        X = universe.cluster_benchmarks; n = X.shape[1]
        if n <= 0: return pd.Series(dtype=float, index=X.columns)
        if n == 1: return pd.Series([1.0], index=X.columns)
        
        cap = _effective_cap(request.cluster_cap, n)
        cov = _cov_shrunk(X, kappa_thresh=request.kappa_shrinkage_threshold, default_shrinkage=request.default_shrinkage_intensity)
        
        if request.profile == "equal_weight": return pd.Series(1.0 / n, index=X.columns)
        if request.profile == "hrp":
            link = linkage(squareform(np.sqrt(0.5 * (1 - X.corr().values.clip(-1, 1))), checks=False), method="ward")
            w_np = _get_recursive_bisection_weights(cov, cast(List[int], pd.Series(sch.leaves_list(link)).tolist()))
            return _enforce_cap_series(pd.Series(w_np, index=X.columns), cap)
            
        l2 = {"EXPANSION": 0.05, "INFLATIONARY_TREND": 0.10, "STAGNATION": 0.10, "CRISIS": 0.20}.get(request.market_environment, 0.05)
        p_w = None
        if request.prev_weights is not None and not request.prev_weights.empty:
            p_w = np.zeros(n)
            for sym_key, weight in request.prev_weights.items():
                c_id = universe.symbol_to_cluster.get(str(sym_key))
                if c_id and f"Cluster_{c_id}" in X.columns: p_w[X.columns.get_loc(f"Cluster_{c_id}")] += float(weight)
            if p_w.sum() > 0: p_w /= p_w.sum()
            
        mu = np.asarray(X.mean(), dtype=float).flatten() * 252
        w = _solve_cvxpy(n=n, cap=cap, cov=cov, mu=mu, penalties=_cluster_penalties(universe), profile=request.profile, risk_free_rate=float(request.risk_free_rate), prev_weights=p_w, l2_gamma=l2)
        return _safe_series(w, X.columns)

    def _barbell(self, *, universe, meta, stats, request) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
        if stats is None or stats.empty: 
            return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["missing stats"]
            
        stats_l = stats.copy()
        if "Symbol" not in stats_l.columns:
            stats_l["Symbol"] = stats_l.index

        if "Antifragility_Score" not in stats_l.columns:
            return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["Antifragility_Score missing"]
            
        stats_l["Cluster_ID"] = stats_l["Symbol"].apply(lambda s: universe.symbol_to_cluster.get(str(s)))
        stats_l = stats_l.dropna(subset=["Cluster_ID"])
        if stats_l.empty: return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["no mapping"]
        
        ranked = stats_l.sort_values("Antifragility_Score", ascending=False).groupby("Cluster_ID").first().sort_values("Antifragility_Score", ascending=False)
        m_a_c = min(min(int(request.max_aggressor_clusters), max(1, len(ranked) // 2)), len(ranked) - 1)
        
        if m_a_c <= 0: 
            return (
                _weights_df_from_cluster_weights(universe=universe, cluster_weights=self._optimize_cluster_weights(universe=universe, request=dataclasses.replace(request, profile="hrp")), meta=meta),
                {"backend": "custom"},
                ["barbell fallback"],
            )
            
        agg_syms = [str(s) for s in ranked.head(m_a_c)["Symbol"].tolist()]
        agg_total = {"QUIET": 0.15, "NORMAL": 0.10, "TURBULENT": 0.05, "CRISIS": 0.03}.get(request.regime, float(request.aggressor_weight))
        agg_per = max(0.0, min(0.95, agg_total)) / len(agg_syms); excluded = [s for c_id in ranked.head(m_a_c).index for s in universe.clusters.get(str(c_id), [])]
        core_syms = [s for s in universe.returns.columns if s not in excluded]
        
        if not core_syms: return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["no core"]
        
        c_prof = "hrp" if len(core_syms) >= 10 else "equal_weight"
        c_u = build_clustered_universe(
            returns=universe.returns,
            clusters={c_id: [s for s in syms if s in core_syms] for c_id, syms in universe.clusters.items() if str(c_id) not in ranked.head(m_a_c).index},
            meta=meta,
            stats=stats,
        )
        c_w_df = _weights_df_from_cluster_weights(
            universe=c_u, cluster_weights=self._optimize_cluster_weights(universe=c_u, request=dataclasses.replace(request, profile=c_prof)), meta=meta, scale=(1.0 - agg_total)
        )
        
        agg_rows = [
            {
                "Symbol": s,
                "Weight": agg_per,
                "Net_Weight": agg_per * (1.0 if (meta or {}).get(s, {}).get("direction", "LONG") == "LONG" else -1.0),
                "Direction": (meta or {}).get(s, {}).get("direction", "LONG"),
                "Cluster_ID": str(universe.symbol_to_cluster.get(s)),
                "Type": "AGGRESSOR",
                "Description": (meta or {}).get(s, {}).get("description", "N/A"),
                "Sector": (meta or {}).get(s, {}).get("sector", "N/A"),
                "Market": (meta or {}).get(s, {}).get("market", "UNKNOWN"),
            }
            for s in agg_syms
        ]
        combined = pd.concat([pd.DataFrame(agg_rows), c_w_df], ignore_index=True)
        combined["Weight"] /= float(combined["Weight"].sum()) + 1e-12
        return combined, {"backend": "custom", "aggressor_clusters": ranked.head(m_a_c).index.tolist()}, []
