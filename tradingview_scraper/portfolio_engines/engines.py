from __future__ import annotations

import importlib.util
import inspect
import logging
from typing import Any, Dict, List, Optional, Tuple, cast

import cvxpy as cp
import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import ledoit_wolf

from tradingview_scraper.portfolio_engines.base import BaseRiskEngine, EngineRequest, EngineResponse, ProfileName
from tradingview_scraper.portfolio_engines.cluster_adapter import ClusteredUniverse, build_clustered_universe
from tradingview_scraper.settings import get_settings

logger = logging.getLogger(__name__)


def _effective_cap(cluster_cap: float, n: int) -> float:
    if n <= 0:
        return 1.0
    return float(max(cluster_cap, 1.0 / n))


def _safe_series(values: np.ndarray, index: pd.Index) -> pd.Series:
    if len(index) != len(values):
        raise ValueError("weights and index size mismatch")
    if len(index) == 0:
        return pd.Series(dtype=float, index=index)
    s = pd.Series(values, index=index)
    s = s.fillna(0.0)
    if float(s.sum()) <= 0:
        return pd.Series(1.0 / len(index), index=index) if len(index) > 0 else pd.Series(dtype=float, index=index)
    return s / float(s.sum())


def _project_capped_simplex(values: np.ndarray, cap: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    if n <= 0:
        return arr
    if n == 1:
        return np.array([1.0])

    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    cap = _effective_cap(cap, n)

    lo = float(arr.min() - cap)
    hi = float(arr.max())

    for _ in range(60):
        mid = (lo + hi) / 2.0
        w = np.minimum(cap, np.maximum(0.0, arr - mid))
        if float(w.sum()) > 1.0:
            lo = mid
        else:
            hi = mid

    w = np.minimum(cap, np.maximum(0.0, arr - hi))
    s = float(w.sum())
    if s <= 0:
        return np.array([1.0 / n] * n)

    residual = 1.0 - s
    if abs(residual) > 1e-9:
        if residual > 0:
            slack = cap - w
            i = int(np.argmax(slack))
            w[i] = min(cap, w[i] + residual)
        else:
            i = int(np.argmax(w))
            w[i] = max(0.0, w[i] + residual)

    return w


def _enforce_cap_series(weights: pd.Series, cap: float) -> pd.Series:
    w = _project_capped_simplex(np.asarray(weights, dtype=float), cap)
    return pd.Series(w, index=weights.index)


def _get_recursive_bisection_weights(cov: np.ndarray, sort_ix: List[int]) -> np.ndarray:
    """
    Standard Lopez de Prado Recursive Bisection for HRP.
    """
    weights = np.ones(len(sort_ix))
    items = [sort_ix]
    while len(items) > 0:
        items = [i[j:k] for i in items for j, k in ((0, len(i) // 2), (len(i) // 2, len(i))) if len(i) > 1]
        for i in range(0, len(items), 2):
            ix_left = items[i]
            ix_right = items[i + 1]

            cov_left = cov[ix_left][:, ix_left]
            cov_right = cov[ix_right][:, ix_right]

            # Inverse-variance weighting at the node
            vol_left = np.trace(cov_left)
            vol_right = np.trace(cov_right)

            alpha = 1 - vol_left / (vol_left + vol_right)
            weights[ix_left] *= alpha
            weights[ix_right] *= 1 - alpha
    return weights


def _weights_df_from_cluster_weights(
    *,
    universe: ClusteredUniverse,
    cluster_weights: pd.Series,
    meta: Optional[Dict[str, Any]],
    scale: float = 1.0,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    meta = meta or {}

    for cluster_col, c_weight in cluster_weights.items():
        if float(c_weight) <= 0:
            continue
        c_id = str(cluster_col).replace("Cluster_", "")
        intra = universe.intra_cluster_weights.get(c_id)
        if intra is None or intra.empty:
            continue

        for sym, sym_w in intra.items():
            w = float(c_weight) * float(sym_w) * scale
            if w <= 1e-9:
                continue

            m = meta.get(str(sym), {}) if isinstance(meta, dict) else {}
            direction = str(m.get("direction", "LONG"))
            rows.append(
                {
                    "Symbol": str(sym),
                    "Weight": float(w),
                    "Net_Weight": float(w) * (1.0 if direction == "LONG" else -1.0),
                    "Direction": direction,
                    "Cluster_ID": str(c_id),
                    "Cluster_Weight": float(c_weight) * scale,
                    "Intra_Cluster_Weight": float(sym_w),
                    "Type": "CORE",
                    "Description": m.get("description", "N/A"),
                    "Sector": m.get("sector", "N/A"),
                    "Market": m.get("market", "UNKNOWN"),
                }
            )

    if not rows:
        return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"]))

    df = pd.DataFrame(rows).sort_values("Weight", ascending=False)

    total = float(df["Weight"].sum())
    if total > 0:
        factor = scale / (total + 1e-12)
        df["Weight"] = df["Weight"] * factor
        if "Net_Weight" in df.columns:
            df["Net_Weight"] = df["Net_Weight"] * factor

    return df


def _cluster_penalties(universe: ClusteredUniverse) -> np.ndarray:
    penalties: List[float] = []
    for c_col in universe.cluster_benchmarks.columns:
        c_id = str(c_col).replace("Cluster_", "")
        penalties.append(float(universe.cluster_stats.get(c_id, {}).get("fragility", 1.0)))
    return np.array(penalties)


def _cov_shrunk(returns: pd.DataFrame) -> np.ndarray:
    """Computes robust covariance matrix using Ledoit-Wolf shrinkage."""
    if returns.shape[1] < 2:
        return returns.cov().values * 252

    shrunk_cov, _ = ledoit_wolf(returns.values)
    return shrunk_cov * 252


def _solve_sharpe_fractional(
    *,
    n: int,
    cap: float,
    cov: np.ndarray,
    mu: np.ndarray,
    risk_free_rate: float = 0.0,
    l2_gamma: float = 0.05,
    solver: Optional[str] = None,
    solver_options: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Direct Sharpe Ratio maximization via Charnes-Cooper transformation."""
    if n <= 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])

    y = cp.Variable(n)
    kappa = cp.Variable(1)
    mu_adj = mu - risk_free_rate

    # Regularize covariance for numerical stability
    cov_reg = cov + np.eye(n) * 1e-6
    risk = cp.quad_form(y, cov_reg)

    ridge = float(max(l2_gamma, 0.0))
    obj = cp.Minimize(risk + ridge * cp.sum_squares(y))
    constraints = [mu_adj @ y == 1, cp.sum(y) == kappa, y >= 0, y <= cap * kappa, kappa >= 0]

    try:
        prob = cp.Problem(obj, constraints)
        active_solver = None
        if solver:
            active_solver = getattr(cp, solver.upper(), None)
        if not active_solver:
            if importlib.util.find_spec("clarabel"):
                active_solver = cp.CLARABEL
            else:
                active_solver = cp.OSQP

        options = solver_options or {}
        prob.solve(solver=active_solver, **options)
        if y.value is None or prob.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
            return np.array([1.0 / n] * n)
        weights = y.value / kappa.value
        return np.array(weights).flatten()
    except Exception:
        return np.array([1.0 / n] * n)


def _solve_cvxpy(
    *,
    n: int,
    cap: float,
    cov: np.ndarray,
    mu: Optional[np.ndarray] = None,
    penalties: Optional[np.ndarray] = None,
    profile: str = "min_variance",
    risk_free_rate: float = 0.0,
    prev_weights: Optional[np.ndarray] = None,
    l2_gamma: float = 0.0,
    solver: Optional[str] = None,
    solver_options: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    if n <= 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])

    w = cp.Variable(n)
    constraints = [cp.sum(w) == 1.0, w >= 0.0, w <= cap]

    # Regularize covariance for numerical stability
    cov_reg = cov + np.eye(n) * 1e-6
    risk = cp.quad_form(w, cov_reg)

    p_term = (w @ penalties) * 0.2 if penalties is not None else 0.0
    l2_term = l2_gamma * cp.sum_squares(w) if l2_gamma > 0 else 0.0
    t_penalty = 0.0
    settings = get_settings()
    if settings.features.feat_turnover_penalty and prev_weights is not None and prev_weights.size == n:
        t_penalty = cp.norm(w - prev_weights, 1) * 0.001

    if profile == "min_variance":
        obj = cp.Minimize(risk + p_term + t_penalty + l2_term)
    elif profile == "risk_parity":
        obj = cp.Minimize(0.5 * risk - (1.0 / n) * cp.sum(cp.log(w)) + t_penalty + l2_term)
    elif profile == "max_sharpe":
        m = mu if mu is not None else np.zeros(n)
        obj = cp.Maximize((m @ w) - 0.5 * risk - p_term - t_penalty - l2_term)
    else:
        obj = cp.Minimize(risk + t_penalty + l2_term)

    try:
        prob = cp.Problem(obj, constraints)
        active_solver = None
        if solver:
            active_solver = getattr(cp, solver.upper(), None)
        if not active_solver:
            if importlib.util.find_spec("clarabel"):
                active_solver = cp.CLARABEL
            else:
                active_solver = cp.ECOS if profile == "risk_parity" else cp.OSQP
        options = solver_options or {}
        if active_solver == cp.OSQP:
            options.update({"eps_abs": 1e-5, "eps_rel": 1e-5, "max_iter": 10000})
        prob.solve(solver=active_solver, **options)
        if w.value is None or prob.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
            return np.array([1.0 / n] * n)
        return np.array(w.value).flatten()
    except Exception:
        return np.array([1.0 / n] * n)


class MarketBaselineEngine(BaseRiskEngine):
    @property
    def name(self) -> str:
        return "market_baseline"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def optimize(self, *, returns: pd.DataFrame, clusters: Dict[str, List[str]], meta: Optional[Dict[str, Any]], stats: Optional[pd.DataFrame], request: EngineRequest) -> EngineResponse:
        targets = list(returns.columns)
        if not targets:
            return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(), meta={"backend": "market_ew_empty"}, warnings=["empty returns"])

        w = 1.0 / len(targets)
        rows = []
        for s in targets:
            m = (meta or {}).get(str(s), {})
            direction = str(m.get("direction", "LONG"))
            rows.append(
                {
                    "Symbol": str(s),
                    "Weight": w,
                    "Net_Weight": w * (1.0 if direction == "LONG" else -1.0),
                    "Direction": direction,
                    "Cluster_ID": "MARKET_EW",
                    "Description": m.get("description", "N/A"),
                }
            )
        return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(rows), meta={"backend": "market_ew"}, warnings=[])


class CustomClusteredEngine(BaseRiskEngine):
    @property
    def name(self) -> str:
        return "custom"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def optimize(self, *, returns: pd.DataFrame, clusters: Dict[str, List[str]], meta: Optional[Dict[str, Any]], stats: Optional[pd.DataFrame], request: EngineRequest) -> EngineResponse:
        settings = get_settings()

        # 1. MARKET Profile: force SPY only (one asset)
        if request.profile == "market":
            bench_targets = [s for s in settings.benchmark_symbols if s in returns.columns]
            if not bench_targets:
                return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(), meta={"backend": "market_empty"}, warnings=["benchmark symbol missing"])

            w = 1.0 / len(bench_targets)
            rows = []
            for s in bench_targets:
                m = (meta or {}).get(str(s), {})
                rows.append(
                    {
                        "Symbol": str(s),
                        "Weight": w,
                        "Net_Weight": w * (1.0 if m.get("direction", "LONG") == "LONG" else -1.0),
                        "Direction": m.get("direction", "LONG"),
                        "Cluster_ID": "MARKET",
                        "Description": m.get("description", "N/A"),
                    }
                )
            return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(rows), meta={"backend": "market_static"}, warnings=[])

        # 2. BENCHMARK Profile: equal-weight risk profile
        if request.profile == "benchmark":
            targets = list(returns.columns)
            if not targets:
                return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(), meta={"backend": "benchmark_empty"}, warnings=["empty returns"])

            w = 1.0 / len(targets)
            rows = []
            for s in targets:
                m = (meta or {}).get(str(s), {})
                rows.append(
                    {
                        "Symbol": str(s),
                        "Weight": w,
                        "Net_Weight": w * (1.0 if m.get("direction", "LONG") == "LONG" else -1.0),
                        "Direction": m.get("direction", "LONG"),
                        "Cluster_ID": "BENCHMARK",
                        "Description": m.get("description", "N/A"),
                    }
                )
            return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(rows), meta={"backend": "benchmark_ew"}, warnings=[])

        # Standard clustered optimization for other profiles
        universe = build_clustered_universe(returns=returns, clusters=clusters, meta=meta, stats=stats)
        if universe.cluster_benchmarks.empty:
            return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), meta={"backend": "custom"}, warnings=["empty universe"])

        if request.profile == "barbell":
            weights_df, meta_out, warn = self._barbell(universe=universe, meta=meta, stats=stats, request=request)
            return EngineResponse(engine=self.name, request=request, weights=weights_df, meta=meta_out, warnings=warn)

        cluster_weights = self._optimize_cluster_weights(universe=universe, request=request)
        weights_df = _weights_df_from_cluster_weights(universe=universe, cluster_weights=cluster_weights, meta=meta)
        return EngineResponse(engine=self.name, request=request, weights=weights_df, meta={"backend": "custom"}, warnings=[])

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        X = universe.cluster_benchmarks
        n = X.shape[1]
        if n <= 0:
            return pd.Series(dtype=float, index=X.columns)
        if n == 1:
            return pd.Series([1.0], index=X.columns)
        cap = _effective_cap(request.cluster_cap, n)
        cov = _cov_shrunk(X)
        mu_eq = cast(Any, np.asarray(X.mean(), dtype=float)) * 252
        penalties = _cluster_penalties(universe)
        mu = mu_eq

        if request.profile == "equal_weight":
            return pd.Series(1.0 / n, index=X.columns)

        if request.profile == "hrp":
            # PURE CUSTOM HRP: Implementation of Lopez de Prado Recursive Bisection
            # Optimized for Jan 2026: Using 'ward' linkage for more robust clusters
            corr = X.corr().values
            dist = np.sqrt(0.5 * (1 - corr.clip(-1, 1)))
            # Ward linkage tends to produce more balanced and significant clusters than single linkage
            link = linkage(squareform(dist, checks=False), method="ward")

            # Quasi-diagonalization
            sort_ix = cast(List[int], pd.Series(sch.leaves_list(link)).tolist())

            # Recursive Bisection
            weights_np = _get_recursive_bisection_weights(cov, sort_ix)
            return _enforce_cap_series(pd.Series(weights_np, index=X.columns), cap)

        req_any = cast(Any, request)
        l2_gamma = {"EXPANSION": 0.05, "INFLATIONARY_TREND": 0.10, "STAGNATION": 0.10, "CRISIS": 0.20}.get(req_any.market_environment, 0.05)
        p_weights_np = None
        if request.prev_weights is not None and not request.prev_weights.empty:
            p_weights_np = np.zeros(n)
            for sym, weight in request.prev_weights.items():
                c_id = universe.symbol_to_cluster.get(str(sym))
                if c_id is not None:
                    try:
                        c_col = f"Cluster_{c_id}"
                        if c_col in X.columns:
                            p_weights_np[X.columns.get_loc(c_col)] += float(weight)
                    except Exception:
                        pass
            s = float(p_weights_np.sum())
            if s > 0:
                p_weights_np = p_weights_np / s
        if request.profile == "max_sharpe":
            w = _solve_sharpe_fractional(
                n=n,
                cap=cap,
                cov=cov,
                mu=mu,
                risk_free_rate=request.risk_free_rate,
                l2_gamma=float(request.l2_gamma),
            )
        else:
            w = _solve_cvxpy(n=n, cap=cap, cov=cov, mu=mu, penalties=penalties, profile=request.profile, risk_free_rate=request.risk_free_rate, prev_weights=p_weights_np, l2_gamma=l2_gamma)
        return _safe_series(w, X.columns)

    def _barbell(self, *, universe: ClusteredUniverse, meta: Optional[Dict[str, Any]], stats: Optional[pd.DataFrame], request: EngineRequest) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
        if stats is None or stats.empty or "Symbol" not in stats.columns or "Antifragility_Score" not in stats.columns:
            return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["missing stats"]
        stats_local = stats.copy()
        stats_local["Cluster_ID"] = stats_local["Symbol"].apply(lambda s: universe.symbol_to_cluster.get(str(s)))
        stats_local = stats_local.dropna(subset=["Cluster_ID"])
        if stats_local.empty:
            return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["no mapping"]
        best_per_cluster = stats_local.sort_values("Antifragility_Score", ascending=False).groupby("Cluster_ID").first()
        ranked = best_per_cluster.sort_values("Antifragility_Score", ascending=False)

        # Dynamic Aggressor Cap: Ensure we don't consume all clusters as aggressors.
        # Goal: Keep at least 50% of clusters for CORE, but no more than request.max_aggressor_clusters.
        n_clusters = len(ranked)
        target_aggressor_count = min(int(request.max_aggressor_clusters), max(1, n_clusters // 2))

        max_aggressor_clusters = min(target_aggressor_count, n_clusters - 1)
        if max_aggressor_clusters <= 0:
            fallback_weights = self._optimize_cluster_weights(
                universe=universe,
                request=EngineRequest(profile="hrp", cluster_cap=request.cluster_cap, risk_free_rate=request.risk_free_rate),
            )
            fallback_df = _weights_df_from_cluster_weights(universe=universe, cluster_weights=fallback_weights, meta=meta)
            return fallback_df, {"backend": "custom"}, ["barbell fallback: insufficient clusters for core"]

        top_clusters = ranked.head(max_aggressor_clusters)
        aggressor_symbols = [str(s) for s in top_clusters["Symbol"].tolist()]
        aggressor_cluster_ids = [str(c) for c in top_clusters.index.tolist()]
        if not aggressor_symbols:
            return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["no aggressors"]
        agg_total = float(request.aggressor_weight)
        if request.aggressor_weight == EngineRequest.aggressor_weight:
            agg_total = {"QUIET": 0.15, "NORMAL": 0.10, "TURBULENT": 0.05, "CRISIS": 0.03}.get(request.regime, agg_total)
        agg_total = max(0.0, min(0.95, agg_total))
        agg_per = agg_total / len(aggressor_symbols)
        excluded = []
        for c_id in aggressor_cluster_ids:
            excluded.extend(universe.clusters.get(str(c_id), []))
        core_symbols = [s for s in universe.returns.columns if s not in excluded]
        if len(core_symbols) < 1:
            return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"])), {"backend": "custom"}, ["no core"]

        # Diversity Floor: If core universe is too small, fallback to Equal Weight for the core layer
        # to prevent HRP collapse into a single asset.
        core_profile = "hrp"
        if len(core_symbols) < 5:
            logger.warning("Diversity Floor Triggered: core_symbols n=%s < 5; using Equal Weight for core.", len(core_symbols))
            core_profile = "equal_weight"

        core_clusters = {c_id: [s for s in syms if s in core_symbols] for c_id, syms in universe.clusters.items() if str(c_id) not in aggressor_cluster_ids}
        core_clusters = {c_id: syms for c_id, syms in core_clusters.items() if syms}
        core_universe = build_clustered_universe(returns=universe.returns, clusters=core_clusters, meta=meta, stats=stats)
        core_cluster_weights = self._optimize_cluster_weights(
            universe=core_universe, request=EngineRequest(profile=core_profile, cluster_cap=request.cluster_cap, risk_free_rate=request.risk_free_rate)
        )
        core_weights_df = _weights_df_from_cluster_weights(universe=core_universe, cluster_weights=core_cluster_weights, meta=meta, scale=(1.0 - agg_total))
        agg_rows = []
        for sym in aggressor_symbols:
            m = (meta or {}).get(sym, {})
            direction = str(m.get("direction", "LONG"))
            agg_rows.append(
                {
                    "Symbol": sym,
                    "Weight": agg_per,
                    "Net_Weight": agg_per * (1.0 if direction == "LONG" else -1.0),
                    "Direction": direction,
                    "Cluster_ID": str(universe.symbol_to_cluster.get(sym)),
                    "Type": "AGGRESSOR",
                    "Description": m.get("description", "N/A"),
                    "Sector": m.get("sector", "N/A"),
                    "Market": m.get("market", "UNKNOWN"),
                }
            )
        combined = pd.concat([pd.DataFrame(agg_rows), core_weights_df], ignore_index=True)
        combined["Weight"] = combined["Weight"] / (float(combined["Weight"].sum()) + 1e-12)
        return combined, {"backend": "custom", "aggressor_clusters": aggressor_cluster_ids}, []


class SkfolioEngine(CustomClusteredEngine):
    @property
    def name(self) -> str:
        return "skfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("skfolio"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        from skfolio.measures import RiskMeasure
        from skfolio.optimization import HierarchicalRiskParity, MeanRisk, ObjectiveFunction, RiskBudgeting

        X = universe.cluster_benchmarks
        n = X.shape[1]
        if n <= 0:
            return pd.Series(dtype=float, index=X.columns)
        if n == 1:
            return pd.Series([1.0], index=X.columns)

        # Small-n policy: skfolio HRP can be brittle for tiny universes (n=2). Default to our
        # custom HRP implementation to keep behavior deterministic and avoid internal failures.
        if request.profile == "hrp" and n < 3:
            logger.warning("skfolio hrp: cluster_benchmarks n=%s < 3; using custom HRP fallback.", n)
            return super()._optimize_cluster_weights(universe=universe, request=request)

        # Native skfolio implementations for core profiles
        if request.profile == "equal_weight":
            from skfolio.optimization import EqualWeighted

            model = EqualWeighted()
        elif request.profile == "hrp":
            # skfolio native HRP
            # Optimized skfolio HRP parameters found via Multi-Objective Optuna (Jan 2026 - v2)
            # Best Balance: linkage='ward', risk_measure='standard_deviation', distance='distance_correlation'
            from skfolio.cluster import HierarchicalClustering, LinkageMethod
            from skfolio.distance import DistanceCorrelation

            model = HierarchicalRiskParity(
                risk_measure=RiskMeasure.STANDARD_DEVIATION, distance_estimator=DistanceCorrelation(), hierarchical_clustering_estimator=HierarchicalClustering(linkage_method=LinkageMethod.WARD)
            )
        elif request.profile == "risk_parity":
            # Risk Parity via equal risk budgeting in skfolio
            model = RiskBudgeting(risk_measure=RiskMeasure.VARIANCE)
        elif request.profile == "max_sharpe":
            model = MeanRisk(objective_function=ObjectiveFunction.MAXIMIZE_RATIO, risk_measure=RiskMeasure.VARIANCE, l2_coef=float(request.l2_gamma))
        else:
            model = MeanRisk(objective_function=ObjectiveFunction.MINIMIZE_RISK, risk_measure=RiskMeasure.VARIANCE)

        cap = _effective_cap(request.cluster_cap, n)
        try:
            sig = inspect.signature(model.__class__)
            if "max_weights" in sig.parameters:
                model.set_params(max_weights=cap)
        except Exception:
            pass

        try:
            model.fit(X)
            raw = cast(Dict[Any, Any], model.weights_)
            if isinstance(raw, dict):
                w = np.array([float(raw.get(str(k), 0.0)) for k in X.columns])
            else:
                w = np.asarray(raw, dtype=float)
                if w.size != n:
                    w = np.array([1.0 / n] * n)
            return _enforce_cap_series(pd.Series(w, index=X.columns).fillna(0.0), cap)
        except Exception as e:
            if request.profile == "hrp":
                logger.warning("skfolio hrp failed (n=%s): %s; using custom HRP fallback.", n, e)
                return super()._optimize_cluster_weights(universe=universe, request=request)
            logger.warning("skfolio optimize failed (profile=%s, n=%s): %s; falling back to equal-weight.", request.profile, n, e)
            return _enforce_cap_series(pd.Series([1.0 / n] * n, index=X.columns), cap)


class PyPortfolioOptEngine(CustomClusteredEngine):
    @property
    def name(self) -> str:
        return "pyportfolioopt"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("pypfopt"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        from pypfopt import EfficientFrontier, HRPOpt, objective_functions

        X = universe.cluster_benchmarks
        n = X.shape[1]
        if n <= 0:
            return pd.Series(dtype=float, index=X.columns)
        if n == 1:
            return pd.Series([1.0], index=X.columns)
        cap = _effective_cap(request.cluster_cap, n)

        if request.profile == "hrp":
            # Pass shrunk covariance to HRPOpt to match Custom/CVX behavior
            cov = _cov_shrunk(X)
            # pypfopt expects a DataFrame for covariance if returns is a DataFrame
            cov_df = pd.DataFrame(cov, index=X.columns, columns=X.columns)
            hrp = HRPOpt(returns=X, cov_matrix=cov_df)
            linkage = str(request.bayesian_params.get("hrp_linkage", "single"))
            weights = hrp.optimize(linkage_method=linkage)
            w = np.array([float(cast(Dict[Any, Any], weights).get(str(k), 0.0)) for k in X.columns])
            s = _safe_series(w, X.columns)
        elif request.profile == "equal_weight":
            return pd.Series(1.0 / n if n > 0 else 0.0, index=X.columns)
        else:
            ef = EfficientFrontier(X.mean() * 252, pd.DataFrame(_cov_shrunk(X), index=X.columns, columns=X.columns), weight_bounds=(0.0, cap))
            ef.add_objective(objective_functions.L2_reg, gamma=float(request.l2_gamma))
            if request.profile == "max_sharpe":
                ef.max_sharpe(risk_free_rate=request.risk_free_rate)
            else:
                ef.min_volatility()
            weights = ef.clean_weights()
            w = np.array([float(cast(Dict[Any, Any], weights).get(str(k), 0.0)) for k in X.columns])
            s = _safe_series(w, X.columns)
        return _enforce_cap_series(s, cap)


class RiskfolioEngine(CustomClusteredEngine):
    @property
    def name(self) -> str:
        return "riskfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("riskfolio"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        import riskfolio as rp

        X = universe.cluster_benchmarks
        n = X.shape[1]
        cap = _effective_cap(request.cluster_cap, n)

        if n <= 0:
            return pd.Series(dtype=float, index=X.columns)
        if n == 1:
            return pd.Series([1.0], index=X.columns)

        # Small-n policy: riskfolio can be brittle for tiny universes (n=2) or when the distance matrix is singular.
        # Default to our custom HRP implementation to keep behavior deterministic.
        if n < 3:
            logger.warning("riskfolio engine: cluster_benchmarks n=%s < 3; using custom HRP fallback.", n)
            return super()._optimize_cluster_weights(universe=universe, request=request)

        if request.profile == "hrp":
            logger.warning("Riskfolio HRP is currently flagged as experimental due to known divergence (-0.95 correlation) with standard implementations.")
            port = rp.HCPortfolio(returns=X)
            # Attempt to align with Custom/Skfolio by using Ward linkage
            w = port.optimization(model="HRP", codependence="pearson", rm="MV", linkage="ward")
        elif request.profile == "risk_parity":
            port = rp.Portfolio(returns=X)
            port.assets_stats(method_mu="hist", method_cov="ledoit")
            w = port.rp_optimization(model="Classic", rm="MV", rf=cast(Any, 0.0), b=None)
        elif request.profile == "equal_weight":
            return pd.Series(1.0 / n if n > 0 else 0.0, index=X.columns)
        else:
            port = rp.Portfolio(returns=X)
            port.assets_stats(method_mu="hist", method_cov="ledoit")
            w = port.optimization(
                model="Classic",
                rm="MV",
                obj="Sharpe" if request.profile == "max_sharpe" else "MinRisk",
                rf=cast(Any, float(request.risk_free_rate)),
                l=cast(Any, float(request.l2_gamma)),
            )

        w_series = w.iloc[:, 0] if isinstance(w, pd.DataFrame) else pd.Series(w)
        return _enforce_cap_series(w_series.reindex(X.columns).fillna(0.0).astype(float), cap)


class CVXPortfolioEngine(CustomClusteredEngine):
    @property
    def name(self) -> str:
        return "cvxportfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("cvxportfolio"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        import cvxportfolio as cvx

        # CVXPortfolio doesn't have native HRP or ERC (Risk Parity).
        # Delegate these to the Custom engine (which uses scipy/cvxpy correct implementations).
        if request.profile in ["hrp", "risk_parity"]:
            return super()._optimize_cluster_weights(universe=universe, request=request)

        X = universe.cluster_benchmarks.copy()
        X = X.replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if X.empty:
            return super()._optimize_cluster_weights(universe=universe, request=request)

        X = X.clip(lower=-0.5, upper=0.5)
        vars = X.var()
        min_var = float(np.min(vars)) if not X.empty else 0.0
        if min_var < 1e-10:
            rows, cols = X.shape
            jitter = 1e-6 * np.sin(np.add.outer(np.arange(rows), np.arange(cols)))
            X = X + jitter
        n = X.shape[1]
        cap = _effective_cap(request.cluster_cap, n)

        if request.profile == "min_variance":
            obj = -100.0 * cvx.FullCovariance()
        elif request.profile == "max_sharpe":
            obj = cvx.ReturnsForecast() - 1.0 * cvx.FullCovariance() - 0.01 * cvx.StocksTransactionCost()
        elif request.profile == "equal_weight":
            return pd.Series(1.0 / n if n > 0 else 0.0, index=X.columns)
        else:
            # Fallback MVO (Risk Averse) for unknown profiles
            obj = cvx.ReturnsForecast() - 5.0 * cvx.FullCovariance() - 0.01 * cvx.StocksTransactionCost()

        constraints = [cvx.LongOnly(), cvx.LeverageLimit(1.0)]
        if hasattr(cvx, "MaxWeights"):
            constraints.append(cvx.MaxWeights(cap))

        try:
            weights = cvx.SinglePeriodOptimization(obj, constraints).values_in_time(
                t=X.index[-1],
                current_weights=pd.Series(1.0 / n, index=X.columns),
                current_portfolio_value=1.0,
                past_returns=X,
                past_volumes=None,
                current_prices=pd.Series(1.0, index=X.columns),
            )
        except Exception:
            return super()._optimize_cluster_weights(universe=universe, request=request)

        s = weights.reindex(X.columns).fillna(0.0).astype(float) if isinstance(weights, pd.Series) else pd.Series(weights, index=X.columns).fillna(0.0).astype(float)
        return _enforce_cap_series(s, cap)


class AdaptiveMetaEngine(BaseRiskEngine):
    @property
    def name(self) -> str:
        return "adaptive"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def optimize(self, *, returns: pd.DataFrame, clusters: Dict[str, List[str]], meta: Optional[Dict[str, Any]], stats: Optional[pd.DataFrame], request: EngineRequest) -> EngineResponse:
        mapping: Dict[str, ProfileName] = {
            "EXPANSION": cast(ProfileName, "max_sharpe"),
            "INFLATIONARY_TREND": cast(ProfileName, "barbell"),
            "NORMAL": cast(ProfileName, "max_sharpe"),
            "STAGNATION": cast(ProfileName, "min_variance"),
            "TURBULENT": cast(ProfileName, "hrp"),
            "CRISIS": cast(ProfileName, "hrp"),
        }
        req_any = cast(Any, request)
        prof = mapping.get(req_any.market_environment, "benchmark")
        base = "skfolio" if req_any.engine == "adaptive" else req_any.engine
        logger.info(f"Adaptive Engine: Switching to {prof} ({req_any.market_environment}) using backend: {base}")
        import dataclasses

        try:
            engine = build_engine(base)
        except Exception:
            engine = CustomClusteredEngine()
        resp = engine.optimize(returns=returns, clusters=clusters, meta=meta, stats=stats, request=dataclasses.replace(request, profile=prof))
        resp.meta.update({"adaptive_profile": prof, "adaptive_base": base})
        return resp


_ENGINE_CLASSES = {
    "market": MarketBaselineEngine,
    "custom": CustomClusteredEngine,
    "skfolio": SkfolioEngine,
    "riskfolio": RiskfolioEngine,
    "pyportfolioopt": PyPortfolioOptEngine,
    "cvxportfolio": CVXPortfolioEngine,
    "adaptive": AdaptiveMetaEngine,
}


def list_known_engines() -> List[str]:
    return sorted(_ENGINE_CLASSES.keys())


def list_available_engines() -> List[str]:
    out = []
    for name, cls in _ENGINE_CLASSES.items():
        try:
            if cls.is_available():
                out.append(name)
        except Exception:
            continue
    return sorted(out)


def build_engine(name: str) -> BaseRiskEngine:
    key = name.strip().lower()
    if key not in _ENGINE_CLASSES:
        raise ValueError(f"Unknown engine: {name}")
    return _ENGINE_CLASSES[key]()
