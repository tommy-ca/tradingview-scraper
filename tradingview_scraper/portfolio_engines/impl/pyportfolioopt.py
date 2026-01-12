from __future__ import annotations
import importlib.util
import logging
import warnings
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np
import pandas as pd

from tradingview_scraper.portfolio_engines.base import EngineRequest, EngineResponse, ProfileName, _effective_cap, _safe_series, _enforce_cap_series
from tradingview_scraper.portfolio_engines.impl.custom import CustomClusteredEngine, _cov_shrunk

logger = logging.getLogger(__name__)


class PyPortfolioOptEngine(CustomClusteredEngine):
    @property
    def name(self) -> str:
        return "pyportfolioopt"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("pypfopt"))

    def _optimize_cluster_weights(self, *, universe, request) -> pd.Series:
        from pypfopt import EfficientFrontier, HRPOpt, objective_functions

        X = universe.cluster_benchmarks
        n = X.shape[1]
        if n <= 0:
            return pd.Series(dtype=float, index=X.columns)
        if n == 1:
            return pd.Series([1.0], index=X.columns)

        cap = _effective_cap(request.cluster_cap, n)
        if request.profile == "hrp":
            hrp = HRPOpt(
                returns=X,
                cov_matrix=pd.DataFrame(_cov_shrunk(X, kappa_thresh=request.kappa_shrinkage_threshold, default_shrinkage=request.default_shrinkage_intensity), index=X.columns, columns=X.columns),
            )
            weights = hrp.optimize(linkage_method=str(request.bayesian_params.get("hrp_linkage", "single")))
            s_res = _safe_series(np.array([float(cast(Dict[Any, Any], weights).get(str(k), 0.0)) for k in X.columns]), X.columns)
        elif request.profile == "equal_weight":
            return pd.Series(1.0 / n, index=X.columns)
        else:
            ef = EfficientFrontier(
                X.mean() * 252,
                pd.DataFrame(_cov_shrunk(X, kappa_thresh=request.kappa_shrinkage_threshold, default_shrinkage=request.default_shrinkage_intensity), index=X.columns, columns=X.columns),
                weight_bounds=(0.0, cap),
            )
            ef.add_objective(objective_functions.L2_reg, gamma=float(request.l2_gamma))
            if request.profile == "max_sharpe":
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    ef.max_sharpe(risk_free_rate=float(request.risk_free_rate))
            else:
                ef.min_volatility()
            weights = ef.clean_weights()
            s_res = _safe_series(np.array([float(cast(Dict[Any, Any], weights).get(str(k), 0.0)) for k in X.columns]), X.columns)
        return _enforce_cap_series(s_res, cap)
