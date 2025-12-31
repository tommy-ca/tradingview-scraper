from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

import pandas as pd

ProfileName = Literal["min_variance", "hrp", "max_sharpe", "barbell"]


class EngineUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class EngineRequest:
    profile: ProfileName
    cluster_cap: float = 0.25
    risk_free_rate: float = 0.0
    aggressor_weight: float = 0.10
    max_aggressor_clusters: int = 5
    regime: str = "NORMAL"
    # Optional previous weights for turnover regularization (Symbol -> Weight)
    prev_weights: Optional[pd.Series] = None


@dataclass(frozen=True)
class EngineResponse:
    engine: str
    request: EngineRequest
    weights: pd.DataFrame
    meta: Dict[str, Any]
    warnings: List[str]


class BaseRiskEngine(ABC):
    """Library-agnostic interface for generating portfolio weights.

    Engines should return a DataFrame with at least:
    - Symbol (str)
    - Weight (float)

    Additional columns are allowed and preserved by downstream reporting.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The canonical name of the risk engine."""

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return True if the engine's dependencies are installed."""

    @abstractmethod
    def optimize(
        self,
        *,
        returns: pd.DataFrame,
        clusters: Dict[str, List[str]],
        meta: Optional[Dict[str, Any]],
        stats: Optional[pd.DataFrame],
        request: EngineRequest,
    ) -> EngineResponse:
        """Compute portfolio weights for a given profile."""
