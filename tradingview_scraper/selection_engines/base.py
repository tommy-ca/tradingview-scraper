from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pandas as pd

from tradingview_scraper.utils.clustering import get_hierarchical_clusters, get_robust_correlation

if TYPE_CHECKING:
    from tradingview_scraper.backtest.models import NumericalWorkspace

logger = logging.getLogger("selection_engines")


@dataclass(frozen=True)
class SelectionRequest:
    top_n: int = 2
    threshold: float = 0.5
    max_clusters: int = 25
    min_momentum_score: float = 0.0
    strategy: str = "trend_following"  # CR-270: Strategy-Specific Selection
    # Optional parameters for specific versions
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SelectionResponse:
    winners: list[dict[str, Any]]
    audit_clusters: dict[int, Any]
    spec_version: str  # e.g. '2.0', '3.0'
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # Symbol -> List of veto reasons
    vetoes: dict[str, list[str]] = field(default_factory=dict)
    relaxation_stage: int = 1
    active_thresholds: dict[str, float] = field(default_factory=dict)


class BaseSelectionEngine(ABC):
    """
    Modular interface for 'Natural Selection' algorithms.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the selection specification (e.g. 'v2', 'v3')."""

    @abstractmethod
    def select(
        self,
        returns: pd.DataFrame,
        raw_candidates: list[dict[str, Any]],
        stats_df: pd.DataFrame | None,
        request: SelectionRequest,
        workspace: NumericalWorkspace | None = None,
    ) -> SelectionResponse:
        """
        Execute the selection logic.
        """


# --- Shared Selection Utilities ---

__all__ = [
    "BaseSelectionEngine",
    "SelectionRequest",
    "SelectionResponse",
    "get_robust_correlation",
    "get_hierarchical_clusters",
]
