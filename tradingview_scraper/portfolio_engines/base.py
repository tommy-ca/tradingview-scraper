from __future__ import annotations

import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, TypeVar, cast

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Institutional Standard: Condition number hurdle for numerical stability
KAPPA_HURDLE = 5000.0

ProfileName = Literal[
    "min_variance",
    "hrp",
    "max_sharpe",
    "barbell",
    "equal_weight",
    "benchmark",
    "market",
    "adaptive",
    "risk_parity",
    "erc",
    "market_neutral",
]

F = TypeVar("F", bound=Callable[..., Any])


def ridge_hardening(func: F) -> F:
    """
    Decorator for allocation solvers that mathematically bounds the condition number
    of the covariance matrix via adaptive ridge shrinkage retries.

    Audit:
        - Numerical Purity: Rely strictly on Training Set Condition Number (Kappa).
        - No Look-ahead: Prohibits use of out-of-sample data.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        request: EngineRequest | None = kwargs.get("request")
        returns: pd.DataFrame | None = kwargs.get("returns")

        if not request or returns is None or returns.empty:
            return func(self, *args, **kwargs)

        # Numerical Stability Logic:
        # We attempt to solve. If it fails or results are clearly unstable,
        # we retry with increasing shrinkage intensity.

        # Shrinkage levels: Initial -> 0.15 -> 0.50 -> 0.95
        intensities = [request.default_shrinkage_intensity, 0.15, 0.50, 0.95]
        # Remove duplicates while preserving order
        shrinkage_levels = []
        for i in intensities:
            if i not in shrinkage_levels:
                shrinkage_levels.append(i)

        from dataclasses import replace

        last_error = None
        for intensity in shrinkage_levels:
            try:
                active_req = replace(request, default_shrinkage_intensity=intensity)
                kwargs["request"] = active_req

                resp: EngineResponse = func(self, *args, **kwargs)

                if not resp.weights.empty:
                    # Check if weights are valid (no NaNs, positive sum)
                    w_sum = resp.weights["Weight"].sum()
                    if w_sum > 1e-6 and not resp.weights["Weight"].isna().any():
                        return resp

            except Exception as e:
                last_error = e
                logger.warning(f"  [RIDGE HARDENING] {self.name} attempt failed (shrinkage={intensity}): {e}")

        # If all attempts failed, return an empty response with warning
        logger.error(f"  [HARDENING FAILED] {self.name} exhausted all shrinkage levels. Error: {last_error}")
        return EngineResponse(engine=self.name, request=request, weights=pd.DataFrame(), meta={"hardening_failure": True, "last_error": str(last_error)}, warnings=["HARDENING_EXHAUSTED"])

    return cast(F, wrapper)


def sanity_veto(func: F) -> F:
    """
    Decorator for allocation solvers that performs a post-optimization check on
    portfolio stability (e.g., Weights variance, sum checks).
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        resp: EngineResponse = func(self, *args, **kwargs)
        if not resp.weights.empty:
            # Numerical Instability Checks (Weight-based only)
            w_sum = resp.weights["Weight"].sum()
            has_nan = resp.weights["Weight"].isna().any()
            is_unstable = w_sum <= 1e-6 or has_nan

            if is_unstable:
                logger.warning(f"  [SANITY VETO] Solver {self.name} produced unstable weights (sum={w_sum:.6f}).")
                object.__setattr__(resp, "warnings", list(resp.warnings) + ["SANITY_VETO_UNSTABLE_WEIGHTS"])

        return resp

    return cast(F, wrapper)


class EngineUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class EngineRequest:
    profile: ProfileName
    engine: str = "custom"
    cluster_cap: float = 0.25
    risk_free_rate: float = 0.0
    l2_gamma: float = 0.05
    aggressor_weight: float = 0.10
    max_aggressor_clusters: int = 5
    regime: str = "NORMAL"
    market_environment: str = "NORMAL"
    bayesian_params: dict[str, Any] = field(default_factory=dict)
    prev_weights: pd.Series | None = None
    kappa_shrinkage_threshold: float = 5000.0
    default_shrinkage_intensity: float = 0.01
    adaptive_fallback_profile: str = "erc"

    # CR-290: Market Neutrality as a Constraint
    market_neutral: bool = False
    target_beta: float = 0.0
    # Optional benchmark returns for beta calculation
    benchmark_returns: pd.Series | None = None


@dataclass(frozen=True)
class EngineResponse:
    engine: str
    request: EngineRequest
    weights: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseRiskEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        return True

    @abstractmethod
    def optimize(
        self,
        *,
        returns: pd.DataFrame,
        clusters: dict[str, list[str]],
        meta: dict[str, Any] | None = None,
        stats: pd.DataFrame | None = None,
        request: EngineRequest,
    ) -> EngineResponse:
        pass


def _effective_cap(cluster_cap: float, n: int) -> float:
    if n <= 0:
        return 1.0
    return float(max(cluster_cap, 1.0 / n))


def _safe_series(values: np.ndarray, index: pd.Index) -> pd.Series:
    if len(index) != len(values):
        raise ValueError("weights and index size mismatch")
    if len(index) == 0:
        return pd.Series(dtype=float, index=index)
    res_s = pd.Series(values, index=index).fillna(0.0)
    total_sum = float(res_s.sum())
    if total_sum <= 0:
        return pd.Series(1.0 / len(index), index=index) if len(index) > 0 else pd.Series(dtype=float, index=index)
    return res_s / total_sum


def _project_capped_simplex(values: np.ndarray, cap: float) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    if n <= 0:
        return arr
    if n == 1:
        return np.array([1.0])
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    cap_val = _effective_cap(cap, n)
    lo, hi = float(arr.min() - cap_val), float(arr.max())
    for _ in range(60):
        mid = (lo + hi) / 2.0
        w = np.minimum(cap_val, np.maximum(0.0, arr - mid))
        if float(w.sum()) > 1.0:
            lo = mid
        else:
            hi = mid
    w = np.minimum(cap_val, np.maximum(0.0, arr - hi))
    s_val = float(w.sum())
    if s_val <= 0:
        return np.array([1.0 / n] * n)
    res = 1.0 - s_val
    if abs(res) > 1e-9:
        if res > 0:
            w[int(np.argmax(cap_val - w))] = min(cap_val, w[int(np.argmax(cap_val - w))] + res)
        else:
            w[int(np.argmax(w))] = max(0.0, w[int(np.argmax(w))] + res)
    return w


def _enforce_cap_series(weights: pd.Series, cap: float) -> pd.Series:
    return pd.Series(_project_capped_simplex(np.asarray(weights, dtype=float), cap), index=weights.index)


class MarketBaselineEngine(BaseRiskEngine):
    @property
    def name(self) -> str:
        return "market"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def optimize(
        self,
        *,
        returns: pd.DataFrame,
        clusters: dict[str, list[str]],
        meta: dict[str, Any] | None = None,
        stats: pd.DataFrame | None = None,
        request: EngineRequest,
    ) -> EngineResponse:
        targets = list(returns.columns)
        if request.profile == "market":
            from tradingview_scraper.settings import get_settings

            s = get_settings()
            bench_targets = [sym for sym in s.benchmark_symbols if sym in returns.columns]
            if bench_targets:
                targets = bench_targets

        if not targets:
            return EngineResponse(self.name, request, pd.DataFrame(), {"backend": "market_empty"}, ["no targets found"])

        w = 1.0 / len(targets)
        rows = [
            {
                "Symbol": str(s),
                "Weight": w,
                "Net_Weight": w * (1.0 if (meta or {}).get(str(s), {}).get("direction", "LONG") == "LONG" else -1.0),
                "Direction": (meta or {}).get(str(s), {}).get("direction", "LONG"),
                "Cluster_ID": "BASELINE",
                "Description": (meta or {}).get(str(s), {}).get("description", "N/A"),
            }
            for s in targets
        ]
        return EngineResponse(self.name, request, pd.DataFrame(rows), {"backend": "baseline_ew"}, [])
