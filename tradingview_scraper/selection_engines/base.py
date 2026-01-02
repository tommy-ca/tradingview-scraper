from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass(frozen=True)
class SelectionRequest:
    top_n: int = 2
    threshold: float = 0.5
    max_clusters: int = 25
    min_momentum_score: float = 0.0
    # Optional parameters for specific versions
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SelectionResponse:
    winners: List[Dict[str, Any]]
    audit_clusters: Dict[int, Any]
    spec_version: str  # e.g. '2.0', '3.0'
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    # Symbol -> List of veto reasons
    vetoes: Dict[str, List[str]] = field(default_factory=dict)


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
        raw_candidates: List[Dict[str, Any]],
        stats_df: Optional[pd.DataFrame],
        request: SelectionRequest,
    ) -> SelectionResponse:
        """
        Execute the selection logic.
        """
