from __future__ import annotations
import dataclasses
import importlib.util
import inspect
import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np
import pandas as pd

from tradingview_scraper.portfolio_engines.base import EngineRequest, EngineResponse, ProfileName, _effective_cap, _enforce_cap_series
from tradingview_scraper.portfolio_engines.impl.custom import CustomClusteredEngine

logger = logging.getLogger(__name__)


class SkfolioEngine(CustomClusteredEngine):
    @property
    def name(self) -> str:
        return "skfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("skfolio"))

    def _optimize_cluster_weights(self, *, universe, request) -> pd.Series:
        from skfolio.measures import RiskMeasure
        from skfolio.optimization import HierarchicalRiskParity, MeanRisk, ObjectiveFunction, RiskBudgeting

        X = universe.cluster_benchmarks
        n = X.shape[1]
        if n <= 0:
            return pd.Series(dtype=float, index=X.columns)
        if n == 1:
            return pd.Series([1.0], index=X.columns)

        # SSP Stage 1: If assets too low, fallback to Custom HRP/EW logic
        if request.profile == "hrp" and n < 3:
            return super()._optimize_cluster_weights(universe=universe, request=request)

        if request.profile == "equal_weight":
            from skfolio.optimization import EqualWeighted

            model = EqualWeighted()
        elif request.profile == "hrp":
            from skfolio.cluster import HierarchicalClustering, LinkageMethod
            from skfolio.distance import DistanceCorrelation

            model = HierarchicalRiskParity(
                risk_measure=RiskMeasure.STANDARD_DEVIATION, distance_estimator=DistanceCorrelation(), hierarchical_clustering_estimator=HierarchicalClustering(linkage_method=LinkageMethod.WARD)
            )
        elif request.profile == "risk_parity" or request.profile == "erc":
            model = RiskBudgeting(risk_measure=RiskMeasure.VARIANCE)
        elif request.profile == "max_sharpe":
            model = MeanRisk(objective_function=ObjectiveFunction.MAXIMIZE_RATIO, risk_measure=RiskMeasure.VARIANCE, l2_coef=float(request.l2_gamma))
        else:
            model = MeanRisk(objective_function=ObjectiveFunction.MINIMIZE_RISK, risk_measure=RiskMeasure.VARIANCE)

        cap = _effective_cap(request.cluster_cap, n)
        try:
            if "max_weights" in inspect.signature(model.__class__).parameters:
                model.set_params(max_weights=cap)
        except Exception:
            pass

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=UserWarning)
                model.fit(X)
            raw = cast(Dict[Any, Any], model.weights_)
            w = np.array([float(raw.get(str(k), 0.0)) for k in X.columns]) if isinstance(raw, dict) else np.asarray(raw, dtype=float)
            return _enforce_cap_series(pd.Series(w, index=X.columns).fillna(0.0), cap)
        except Exception:
            # Recursive SSP Fallback
            if request.profile == "max_sharpe":
                return self._optimize_cluster_weights(universe=universe, request=dataclasses.replace(request, profile="min_variance"))
            if request.profile == "hrp":
                return super()._optimize_cluster_weights(universe=universe, request=request)
            return _enforce_cap_series(pd.Series([1.0 / n] * n, index=X.columns), cap)
