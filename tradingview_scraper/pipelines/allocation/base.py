from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
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
    window: Any  # Use Any to avoid circular imports with WalkForwardWindow
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

    def merge(self, overlay: AllocationContext):
        """Merges another context into this one (additive and concatenation)."""
        import pandas as pd

        # 1. Merge Results (Append new entries, avoid duplicates)
        existing_results = {(r.get("window"), r.get("engine"), r.get("profile"), r.get("simulator")) for r in self.results}
        for res in overlay.results:
            key = (res.get("window"), res.get("engine"), res.get("profile"), res.get("simulator"))
            if key not in existing_results:
                self.results.append(res)
                existing_results.add(key)

        # 2. Merge Holdings (Update state mapping)
        if overlay.current_holdings:
            self.current_holdings.update(overlay.current_holdings)

        # 3. Merge Return Series (Combine series lists for each state key)
        for key, series_list in overlay.return_series.items():
            if key not in self.return_series:
                self.return_series[key] = series_list
            else:
                self.return_series[key].extend(series_list)

        # 4. Merge Stats (Concatenate rows and deduplicate)
        if not overlay.stats.empty:
            if self.stats.empty:
                self.stats = overlay.stats
            else:
                self.stats = pd.concat([self.stats, overlay.stats], axis=0).drop_duplicates()

        # 5. Merge Audit Trail (Append only new entries)
        if len(overlay.audit_trail) > len(self.audit_trail):
            new_entries = overlay.audit_trail[len(self.audit_trail) :]
            self.audit_trail.extend(new_entries)

        # 6. Merge Metadata & Clusters (Dictionaries)
        if overlay.window_meta:
            self.window_meta.update(overlay.window_meta)
        if overlay.clusters:
            self.clusters.update(overlay.clusters)
