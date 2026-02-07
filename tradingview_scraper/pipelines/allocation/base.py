from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from tradingview_scraper.backtest.orchestration import WalkForwardWindow

logger = logging.getLogger("pipelines.allocation")


class AllocationContext(BaseModel):
    """
    The state container for the Allocation Pipeline.
    Encapsulates all necessary data and state for Pillar 3 (Allocation & Simulation).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str

    # Environment & Windows
    window: WalkForwardWindow
    regime_name: str
    market_env: str

    # Data Matrices
    train_rets: pd.DataFrame
    train_rets_strat: pd.DataFrame
    test_rets: pd.DataFrame
    bench_rets: Optional[pd.Series] = None

    # Metadata & Clusters
    clusters: Dict[str, List[str]] = Field(default_factory=dict)
    window_meta: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    stats: pd.DataFrame = Field(default_factory=pd.DataFrame)
    is_meta: bool = False

    # Parameters
    engine_names: List[str] = Field(default_factory=list)
    profiles: List[str] = Field(default_factory=list)
    sim_names: List[str] = Field(default_factory=list)

    # Results & State (Mutable)
    results: List[Dict[str, Any]] = Field(default_factory=list)
    current_holdings: Dict[str, Any] = Field(default_factory=dict)  # State key -> holdings
    return_series: Dict[str, List[pd.Series]] = Field(default_factory=dict)  # State key -> list of returns

    # Audit & Ledger
    ledger: Optional[Any] = None
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)

    def log_event(self, stage: str, event: str, data: Optional[Dict[str, Any]] = None):
        self.audit_trail.append({"stage": stage, "event": event, "data": data or {}})
