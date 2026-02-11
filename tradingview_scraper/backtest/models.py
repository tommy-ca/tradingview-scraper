from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from tradingview_scraper.backtest.orchestration import WalkForwardWindow


@dataclass(slots=True)
class NumericalWorkspace:
    """
    Pre-allocated buffers for backtest hot-loops to eliminate GC pressure.
    (Pillar 3 Standard: Zero-Allocation).
    """

    returns_buf: np.ndarray  # Shape: (T, N)
    weights_buf: np.ndarray  # Shape: (N,)
    equity_curve: np.ndarray  # Shape: (T,)

    # Predictability Workspace
    perm_counts: np.ndarray  # Shape: (4000+)
    segment_buffer: np.ndarray  # Shape: (order)

    # Risk state mask (persistent VETOED assets)
    vetoed_mask: np.ndarray  # Shape: (N,)

    @classmethod
    def for_dimensions(cls, n_obs: int, n_assets: int, max_order: int = 5) -> NumericalWorkspace:
        """Initializes buffers with np.empty for maximum efficiency."""
        max_key = int(max_order**max_order)
        buf_size = max(4000, max_key + 1)

        return cls(
            returns_buf=np.empty((n_obs, n_assets), dtype=np.float64),
            weights_buf=np.empty(n_assets, dtype=np.float64),
            equity_curve=np.empty(n_obs, dtype=np.float64),
            perm_counts=np.zeros(buf_size, dtype=np.int32),
            segment_buffer=np.zeros(max_order, dtype=np.float64),
            vetoed_mask=np.zeros(n_assets, dtype=bool),
        )


@dataclass(frozen=True)
class SimulationContext:
    """
    Encapsulates all necessary data and state for a single simulation window.
    Narrowed types for LSP alignment.
    """

    engine_name: str
    profile: str
    window: WalkForwardWindow
    regime_name: str
    market_env: str
    train_rets: pd.DataFrame
    train_rets_strat: pd.DataFrame
    clusters: dict[str, list[str]]
    window_meta: dict[str, dict[str, Any]]  # Map of symbol -> winner metadata
    bench_rets: pd.Series | None
    is_meta: bool
    test_rets: pd.DataFrame
    veto_registry: Any | None = None
