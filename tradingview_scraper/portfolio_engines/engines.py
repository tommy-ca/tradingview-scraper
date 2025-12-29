from __future__ import annotations

import importlib.util
import inspect
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from tradingview_scraper.portfolio_engines.base import BaseRiskEngine, EngineRequest, EngineResponse, EngineUnavailableError
from tradingview_scraper.portfolio_engines.cluster_adapter import ClusteredUniverse, build_clustered_universe


def _effective_cap(cluster_cap: float, n: int) -> float:
    if n <= 0:
        return 1.0
    # Ensure feasibility when n * cap < 1.
    return float(max(cluster_cap, 1.0 / n))


def _safe_series(values: np.ndarray, index: pd.Index) -> pd.Series:
    if len(index) != len(values):
        raise ValueError("weights and index size mismatch")
    s = pd.Series(values, index=index)
    s = s.fillna(0.0)
    if float(s.sum()) <= 0:
        return pd.Series(1.0 / len(index), index=index)
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
                    "Description": m.get("description", "N/A"),
                    "Sector": m.get("sector", "N/A"),
                    "Market": m.get("market", "UNKNOWN"),
                }
            )

    if not rows:
        return pd.DataFrame(columns=pd.Index(["Symbol", "Weight"]))  # minimal contract

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


def _cov_annualized(returns: pd.DataFrame) -> np.ndarray:
    cov = returns.cov() * 252
    return cov.values


def _min_var_obj(weights: np.ndarray, cov: np.ndarray, penalties: Optional[np.ndarray] = None) -> float:
    base_vol = float(np.sqrt(np.dot(weights.T, np.dot(cov, weights))))
    if penalties is None:
        return base_vol
    penalty = float(np.dot(weights, penalties))
    return base_vol * (1.0 + penalty * 0.2)


def _risk_parity_obj(weights: np.ndarray, cov: np.ndarray) -> float:
    vol = float(np.sqrt(np.dot(weights.T, np.dot(cov, weights))))
    if vol <= 0:
        return 0.0
    mrc = np.dot(cov, weights) / vol
    rc = weights * mrc
    target_rc = vol / len(weights)
    return float(np.sum(np.square(rc - target_rc)))


def _max_sharpe_obj(weights: np.ndarray, returns_df: pd.DataFrame, penalties: Optional[np.ndarray] = None, risk_free_rate: float = 0.0) -> float:
    cov = _cov_annualized(returns_df)
    vol = float(np.sqrt(np.dot(weights.T, np.dot(cov, weights))))
    if vol <= 0:
        return 0.0

    mu = returns_df.mean().values * 252
    ret = float(np.sum(mu * weights))
    sharpe = (ret - risk_free_rate) / (vol + 1e-12)

    if penalties is not None:
        penalty = float(np.dot(weights, penalties))
        return float(-(sharpe / (1.0 + penalty * 0.2)))

    return float(-sharpe)


def _solve_slsqp(
    *,
    objective,
    n: int,
    cap: float,
    args: Tuple[Any, ...] = (),
) -> np.ndarray:
    if n <= 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])

    init_weights = np.array([1.0 / n] * n)
    bounds = tuple((0.0, cap) for _ in range(n))
    constraints = {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}

    try:
        res = minimize(objective, init_weights, args=args, method="SLSQP", bounds=bounds, constraints=constraints)
        if not res.success or res.x is None:
            return init_weights
        return cast(np.ndarray, res.x)
    except Exception:
        return init_weights


class CustomClusteredEngine(BaseRiskEngine):
    name = "custom"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def optimize(
        self,
        *,
        returns: pd.DataFrame,
        clusters: Dict[str, List[str]],
        meta: Optional[Dict[str, Any]],
        stats: Optional[pd.DataFrame],
        request: EngineRequest,
    ) -> EngineResponse:
        universe = build_clustered_universe(returns=returns, clusters=clusters, meta=meta, stats=stats)

        warnings: List[str] = []
        if universe.cluster_benchmarks.empty:
            return EngineResponse(
                engine=self.name,
                request=request,
                weights=pd.DataFrame(columns=cast(Any, ["Symbol", "Weight"])),
                meta={"backend": "custom"},
                warnings=["empty universe"],
            )

        profile = request.profile
        if profile == "barbell":
            weights_df, meta_out, warn = self._barbell(universe=universe, meta=meta, stats=stats, request=request)
            return EngineResponse(engine=self.name, request=request, weights=weights_df, meta=meta_out, warnings=warnings + warn)

        cluster_weights = self._optimize_cluster_weights(universe=universe, request=request)
        weights_df = _weights_df_from_cluster_weights(universe=universe, cluster_weights=cluster_weights, meta=meta)
        return EngineResponse(engine=self.name, request=request, weights=weights_df, meta={"backend": "custom"}, warnings=warnings)

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        n = universe.cluster_benchmarks.shape[1]
        cap = _effective_cap(request.cluster_cap, n)
        cov = _cov_annualized(universe.cluster_benchmarks)
        penalties = _cluster_penalties(universe)

        if request.profile == "min_variance":
            w = _solve_slsqp(objective=_min_var_obj, n=n, cap=cap, args=(cov, penalties))
        elif request.profile == "hrp":
            # Our internal baseline uses risk-parity across the hierarchical buckets.
            w = _solve_slsqp(objective=_risk_parity_obj, n=n, cap=cap, args=(cov,))
        elif request.profile == "max_sharpe":
            w = _solve_slsqp(objective=_max_sharpe_obj, n=n, cap=cap, args=(universe.cluster_benchmarks, penalties, request.risk_free_rate))
        else:
            w = np.array([1.0 / n] * n)

        return _safe_series(w, universe.cluster_benchmarks.columns)

    def _barbell(
        self,
        *,
        universe: ClusteredUniverse,
        meta: Optional[Dict[str, Any]],
        stats: Optional[pd.DataFrame],
        request: EngineRequest,
    ) -> Tuple[pd.DataFrame, Dict[str, Any], List[str]]:
        if stats is None or stats.empty or "Symbol" not in stats.columns or "Antifragility_Score" not in stats.columns:
            return pd.DataFrame(columns=["Symbol", "Weight"]), {"backend": "custom"}, ["missing antifragility stats for barbell"]

        # Select top aggressor clusters by best (highest antifragility) symbol.
        sym_to_cluster = universe.symbol_to_cluster
        stats_local = stats.copy()
        stats_local["Cluster_ID"] = stats_local["Symbol"].apply(lambda s: sym_to_cluster.get(str(s)))
        stats_local = stats_local.dropna(subset=["Cluster_ID"])
        if stats_local.empty:
            return pd.DataFrame(columns=["Symbol", "Weight"]), {"backend": "custom"}, ["no cluster mapping for barbell"]

        best_per_cluster = stats_local.sort_values("Antifragility_Score", ascending=False).groupby("Cluster_ID").first()
        top_clusters = best_per_cluster.sort_values("Antifragility_Score", ascending=False).head(request.max_aggressor_clusters)
        aggressor_symbols = [str(s) for s in top_clusters["Symbol"].tolist()]
        aggressor_cluster_ids = [str(c) for c in top_clusters.index.tolist()]

        if not aggressor_symbols:
            return pd.DataFrame(columns=["Symbol", "Weight"]), {"backend": "custom"}, ["no aggressor clusters found"]

        agg_total = float(request.aggressor_weight)
        agg_per = agg_total / len(aggressor_symbols)

        # Exclude full clusters from the core sleeve.
        excluded_symbols: List[str] = []
        for c_id in aggressor_cluster_ids:
            excluded_symbols.extend(universe.clusters.get(str(c_id), []))

        core_symbols = [s for s in universe.returns.columns if s not in excluded_symbols]
        if len(core_symbols) < 2:
            return pd.DataFrame(columns=["Symbol", "Weight"]), {"backend": "custom"}, ["insufficient core symbols after exclusion"]

        # Build a reduced universe for the core sleeve.
        core_clusters = {c_id: [s for s in syms if s in core_symbols] for c_id, syms in universe.clusters.items() if str(c_id) not in aggressor_cluster_ids}
        core_clusters = {c_id: syms for c_id, syms in core_clusters.items() if syms}
        core_universe = build_clustered_universe(returns=universe.returns, clusters=core_clusters, meta=meta, stats=stats)

        # Core sleeve uses internal risk-parity across clusters (baseline behavior).
        core_req = EngineRequest(profile="hrp", cluster_cap=request.cluster_cap, risk_free_rate=request.risk_free_rate)
        core_cluster_weights = self._optimize_cluster_weights(universe=core_universe, request=core_req)
        core_weights_df = _weights_df_from_cluster_weights(universe=core_universe, cluster_weights=core_cluster_weights, meta=meta, scale=(1.0 - agg_total))

        # Aggressor sleeve: equal-weight on the selected top symbols.
        agg_rows: List[Dict[str, Any]] = []
        meta_obj = meta or {}
        for sym in aggressor_symbols:
            m = meta_obj.get(sym, {}) if isinstance(meta_obj, dict) else {}
            direction = str(m.get("direction", "LONG"))
            agg_rows.append(
                {
                    "Symbol": sym,
                    "Weight": float(agg_per),
                    "Net_Weight": float(agg_per) * (1.0 if direction == "LONG" else -1.0),
                    "Direction": direction,
                    "Cluster_ID": str(sym_to_cluster.get(sym, "N/A")),
                    "Cluster_Label": "AGGRESSOR",
                    "Type": "AGGRESSOR (Antifragile)",
                    "Description": m.get("description", "N/A"),
                    "Sector": m.get("sector", "N/A"),
                    "Market": m.get("market", "UNKNOWN"),
                }
            )

        combined = pd.concat([pd.DataFrame(agg_rows), core_weights_df], ignore_index=True)
        combined = combined.sort_values("Weight", ascending=False)
        combined["Weight"] = combined["Weight"] / (float(combined["Weight"].sum()) + 1e-12)

        return combined, {"backend": "custom", "aggressor_clusters": aggressor_cluster_ids}, []


class SkfolioEngine(CustomClusteredEngine):
    name = "skfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("skfolio"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        if not self.is_available():
            raise EngineUnavailableError("skfolio is not installed")

        # skfolio expects returns (not prices) and follows sklearn's API.
        from skfolio.measures import RiskMeasure
        from skfolio.optimization import HierarchicalRiskParity, MeanRisk, ObjectiveFunction

        X = universe.cluster_benchmarks
        n = X.shape[1]
        cap = _effective_cap(request.cluster_cap, n)

        if request.profile == "hrp":
            model = HierarchicalRiskParity(risk_measure=RiskMeasure.VARIANCE)
        else:
            if request.profile == "max_sharpe":
                model = MeanRisk(objective_function=ObjectiveFunction.MAXIMIZE_RATIO, risk_measure=RiskMeasure.VARIANCE)
            else:
                model = MeanRisk(objective_function=ObjectiveFunction.MINIMIZE_RISK, risk_measure=RiskMeasure.VARIANCE)

        # Apply max-weight constraint if supported by the estimator.
        try:
            sig = inspect.signature(model.__class__)
            if "max_weights" in sig.parameters:
                model.set_params(max_weights=cap)
        except Exception:
            pass

        model.fit(X)
        raw = model.weights_
        if isinstance(raw, dict):
            w = np.array([float(raw.get(str(k), 0.0)) for k in X.columns])
        else:
            w = np.asarray(raw, dtype=float)
            if int(w.size) != int(n):
                w = np.array([1.0 / n] * n)

        s = pd.Series(w, index=X.columns).fillna(0.0).astype(float)
        return _enforce_cap_series(s, cap)


class PyPortfolioOptEngine(CustomClusteredEngine):
    name = "pyportfolioopt"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("pypfopt"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        if not self.is_available():
            raise EngineUnavailableError("PyPortfolioOpt (pypfopt) is not installed")

        from pypfopt import EfficientFrontier
        from pypfopt.hierarchical_portfolio import HRPOpt

        X = universe.cluster_benchmarks
        n = X.shape[1]
        cap = _effective_cap(request.cluster_cap, n)

        if request.profile == "hrp":
            hrp = HRPOpt(X)
            weights = hrp.optimize()
            w = np.array([float(weights.get(str(k), 0.0)) for k in X.columns])
            s = _safe_series(w, X.columns)
        else:
            mu = X.mean() * 252
            cov = X.cov() * 252

            ef = EfficientFrontier(mu, cov, weight_bounds=(0.0, cap))
            if request.profile == "max_sharpe":
                ef.max_sharpe(risk_free_rate=request.risk_free_rate)
            else:
                ef.min_volatility()

            weights = ef.clean_weights()
            w = np.array([float(weights.get(str(k), 0.0)) for k in X.columns])
            s = _safe_series(w, X.columns)

        return _enforce_cap_series(s, cap)


class RiskfolioEngine(CustomClusteredEngine):
    name = "riskfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("riskfolio"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        if not self.is_available():
            raise EngineUnavailableError("Riskfolio-Lib (riskfolio) is not installed")

        import riskfolio as rp

        X = universe.cluster_benchmarks
        n = X.shape[1]
        cap = _effective_cap(request.cluster_cap, n)

        if request.profile == "hrp":
            port = rp.HCPortfolio(returns=X)
            w = port.optimization(model="HRP", codependence="pearson", rm="MV")
        else:
            port = rp.Portfolio(returns=X)
            port.assets_stats(method_mu="hist", method_cov="ledoit")

            obj = "MinRisk" if request.profile == "min_variance" else "Sharpe"
            rm = "MV"
            w = port.optimization(model="Classic", rm=rm, obj=obj, rf=request.risk_free_rate, l=0)

        # Riskfolio returns a DataFrame of weights indexed by asset.
        if isinstance(w, pd.DataFrame):
            w_series = w.iloc[:, 0]
        else:
            w_series = pd.Series(w)
        s = w_series.reindex(X.columns).fillna(0.0).astype(float)
        return _enforce_cap_series(s, cap)


class CVXPortfolioEngine(CustomClusteredEngine):
    name = "cvxportfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("cvxportfolio"))

    def _optimize_cluster_weights(self, *, universe: ClusteredUniverse, request: EngineRequest) -> pd.Series:
        if not self.is_available():
            raise EngineUnavailableError("cvxportfolio is not installed")

        import cvxportfolio as cvx

        X = universe.cluster_benchmarks
        n = X.shape[1]
        cap = _effective_cap(request.cluster_cap, n)

        # Build a single-period optimization with mean return forecast and full covariance.
        # Note: cvxportfolio is designed for backtesting with a simulator; here we extract target weights only.
        gamma = 1.0
        objective = cvx.ReturnsForecast() - gamma * cvx.FullCovariance()
        constraints = [cvx.LongOnly(), cvx.LeverageLimit(1.0)]

        # Approximate cap via max weight constraint if available.
        if hasattr(cvx, "MaxWeights"):
            constraints.append(cvx.MaxWeights(cap))

        policy = cvx.SinglePeriodOptimization(objective, constraints)

        # Provide historical returns as the "market data" input.
        # cvxportfolio expects returns as a DataFrame with assets columns.
        # We provide a dummy current state to extract target weights.
        current_weights = pd.Series(1.0 / n, index=X.columns)
        # Add a dummy cash account if not present (cvxportfolio usually expects it)
        # But for SPO it might be okay if we don't have it depending on constraints.
        try:
            weights = policy.values_in_time(
                t=X.index[-1],
                current_weights=current_weights,
                current_portfolio_value=1.0,
                past_returns=X,
                past_volumes=None,
            )
        except Exception:
            # Fallback for older versions or specific failures
            weights = current_weights

        if isinstance(weights, pd.Series):
            s = weights.reindex(X.columns).fillna(0.0).astype(float)
        else:
            s = pd.Series(weights, index=X.columns).fillna(0.0).astype(float)

        return _enforce_cap_series(s, cap)


_ENGINE_CLASSES = {
    "custom": CustomClusteredEngine,
    "skfolio": SkfolioEngine,
    "riskfolio": RiskfolioEngine,
    "pyportfolioopt": PyPortfolioOptEngine,
    "cvxportfolio": CVXPortfolioEngine,
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
        raise ValueError(f"Unknown engine: {name}. Known: {', '.join(list_known_engines())}")
    return _ENGINE_CLASSES[key]()
