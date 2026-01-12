from __future__ import annotations
import importlib.util
import logging
from typing import Any, Dict, List, Optional, Tuple, cast
import numpy as np
import pandas as pd

from tradingview_scraper.portfolio_engines.base import EngineRequest, EngineResponse, ProfileName, _effective_cap, _enforce_cap_series
from tradingview_scraper.portfolio_engines.impl.custom import CustomClusteredEngine

logger = logging.getLogger(__name__)


class CVXPortfolioEngine(CustomClusteredEngine):
    @property
    def name(self) -> str:
        return "cvxportfolio"

    @classmethod
    def is_available(cls) -> bool:
        return bool(importlib.util.find_spec("cvxportfolio"))

    def _optimize_cluster_weights(self, *, universe, request) -> pd.Series:
        import cvxportfolio as cvx

        # HRP/Risk-Parity not natively implemented in CVXPortfolio wrapper yet
        if request.profile in ["hrp", "risk_parity", "erc"]:
            return super()._optimize_cluster_weights(universe=universe, request=request)

        X = universe.cluster_benchmarks.copy().replace([np.inf, -np.inf], np.nan).dropna(how="any")
        if X.empty:
            return super()._optimize_cluster_weights(universe=universe, request=request)

        X = X.clip(lower=-0.5, upper=0.5)
        n = X.shape[1]
        cap = _effective_cap(request.cluster_cap, n)

        if request.profile == "min_variance":
            obj = -100.0 * cvx.FullCovariance()
        elif request.profile == "max_sharpe":
            obj = cvx.ReturnsForecast() - 1.0 * cvx.FullCovariance() - 0.01 * cvx.StocksTransactionCost()
        elif request.profile == "equal_weight":
            return pd.Series(1.0 / n if n > 0 else 0.0, index=X.columns)
        else:
            obj = cvx.ReturnsForecast() - 5.0 * cvx.FullCovariance() - 0.01 * cvx.StocksTransactionCost()

        cons = [cvx.LongOnly(), cvx.LeverageLimit(1.0)]
        if hasattr(cvx, "MaxWeights"):
            cons.append(cvx.MaxWeights(cap))

        try:
            X_cvx = X.copy()
            if not isinstance(X_cvx.index, pd.DatetimeIndex):
                X_cvx.index = pd.to_datetime(X_cvx.index, utc=True)
            if cast(Any, X_cvx.index).tz is None:
                X_cvx = X_cvx.tz_localize("UTC")
            else:
                X_cvx = X_cvx.tz_convert("UTC")

            weights = cvx.SinglePeriodOptimization(obj, cons).values_in_time(
                t=X_cvx.index[-1],
                current_weights=pd.Series(1.0 / n, index=X_cvx.columns),
                current_portfolio_value=1.0,
                past_returns=X_cvx,
                past_volumes=None,
                current_prices=pd.Series(1.0, index=X_cvx.columns),
            )
            res_s = weights.reindex(X.columns).fillna(0.0).astype(float) if isinstance(weights, pd.Series) else pd.Series(weights, index=X.columns).fillna(0.0).astype(float)
            return _enforce_cap_series(res_s, cap)
        except Exception:
            return super()._optimize_cluster_weights(universe=universe, request=request)
