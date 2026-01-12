from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform

from tradingview_scraper.settings import get_settings

logger = logging.getLogger("selection_engines")


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
    relaxation_stage: int = 1
    active_thresholds: Dict[str, float] = field(default_factory=dict)


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


# --- Shared Selection Utilities ---


def get_robust_correlation(returns: pd.DataFrame, shrinkage: float = 0.01) -> pd.DataFrame:
    """
    Computes a shrinkage-adjusted correlation matrix for numerical stability.
    """
    if returns.empty:
        return pd.DataFrame()
    corr = returns.replace(0, np.nan).corr(min_periods=20).fillna(0.0)
    if not corr.empty:
        n = corr.shape[0]
        # Ridge adjustment
        corr = corr * (1.0 - shrinkage) + np.eye(n) * shrinkage
    return corr


def get_hierarchical_clusters(returns: pd.DataFrame, threshold: float = 0.5, max_clusters: int = 25) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes averaged distance matrix and performs Ward Linkage clustering.
    Returns (cluster_ids, linkage_matrix).
    """
    if returns.empty:
        return np.array([]), np.array([])

    settings = get_settings()
    lookbacks = settings.cluster_lookbacks
    available_len = len(returns)
    valid_lookbacks = [l for l in lookbacks if l <= available_len] or [available_len]

    dist_matrices = []
    for l in valid_lookbacks:
        corr = get_robust_correlation(returns.tail(l), shrinkage=settings.features.default_shrinkage_intensity)
        if not corr.empty:
            dist_matrices.append(np.sqrt(0.5 * (1 - corr.values.clip(-1, 1))))

    if not dist_matrices:
        return np.array([1] * len(returns.columns)), np.array([])

    avg_dist = np.mean(dist_matrices, axis=0)
    avg_dist = (avg_dist + avg_dist.T) / 2
    np.fill_diagonal(avg_dist, 0)

    if len(returns.columns) < 2:
        return np.array([1]), np.array([])

    link = sch.linkage(squareform(avg_dist, checks=False), method="ward")
    cluster_ids = sch.fcluster(link, t=threshold, criterion="distance") if threshold > 0 else sch.fcluster(link, t=max_clusters, criterion="maxclust")

    return cluster_ids, link
