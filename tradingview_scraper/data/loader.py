from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.data_utils import ensure_utc_index
from tradingview_scraper.utils.security import SecurityUtils

logger = logging.getLogger(__name__)


class RunData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    returns: pd.DataFrame = Field(default_factory=pd.DataFrame)
    raw_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    features: pd.DataFrame = Field(default_factory=pd.DataFrame)
    stats: pd.DataFrame = Field(default_factory=pd.DataFrame)


class DataLoader:
    """
    Institutional data loader for the quantitative platform.
    Centralizes path resolution, security anchoring, and data integrity.
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def list_available_runs(self) -> list[str]:
        """
        Returns a sorted list of available run IDs from the summaries directory.

        Returns:
            list[str]: Sorted run IDs (newest first).
        """
        runs_dir = self.settings.summaries_runs_dir
        if not runs_dir.exists():
            return []
        return sorted(
            [d.name for d in runs_dir.iterdir() if d.is_dir() and (d / "data").exists()],
            reverse=True,
        )

    def resolve_latest_run_dir(self) -> Path | None:
        """
        Finds the filesystem path of the most recent valid run.

        Returns:
            Path | None: Path to the latest run directory or None if no runs found.
        """
        runs = self.list_available_runs()
        if not runs:
            return None
        return self.settings.summaries_runs_dir / runs[0]

    def ensure_safe_path(self, path: Path | str) -> Path:
        """
        Anchors the requested path to institutional data roots to prevent traversal.

        Args:
            path: Target path to validate.

        Returns:
            Path: Resolved absolute path.

        Audit:
            - Security: Strictly anchored to lakehouse or artifacts roots.
        """
        allowed = [
            self.settings.summaries_runs_dir.resolve(),
            self.settings.lakehouse_dir.resolve(),
            self.settings.artifacts_dir.resolve(),
        ]
        return SecurityUtils.ensure_safe_path(path, allowed)

    def find_latest_run_for_profile(self, profile: str) -> Path | None:
        """
        Finds the latest run directory that was executed with the specified profile.
        Checks both resolved_manifest.json and audit.jsonl for verification.
        """
        runs_dir = self.settings.summaries_runs_dir
        if not runs_dir.exists():
            return None

        # Sort runs by directory name (timestamp) descending
        runs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)

        for run in runs:
            # Priority 1: resolved_manifest.json
            manifest_path = run / "config" / "resolved_manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path, "r") as f:
                        manifest = json.load(f)
                        if manifest.get("profile") == profile:
                            return run
                except Exception:
                    pass

            # Priority 2: audit.jsonl genesis entry
            audit_path = run / "audit.jsonl"
            if audit_path.exists():
                try:
                    with open(audit_path, "r") as f:
                        first_line = f.readline()
                        entry = json.loads(first_line)
                        if entry.get("type") == "genesis" and entry.get("profile") == profile:
                            return run
                except Exception:
                    pass
        return None

    def load_run_data(self, run_dir: Path | None = None, strict: bool = False) -> RunData:
        """
        Orchestrates the deterministic loading of backtest data from run directories.

        Args:
            run_dir: Target directory. Defaults to latest available run.
            strict: If True, only loads from run_dir (no lakehouse fallbacks).

        Returns:
            RunData: Loaded returns, features, stats, and metadata.
        """
        if not run_dir:
            run_dir = self.resolve_latest_run_dir()

        data_dir = (run_dir / "data") if run_dir else self.settings.lakehouse_dir
        logger.info(f"Loading data from {data_dir} (strict={strict})")

        result = RunData()

        # 1. Load Candidates
        cands_priority = [data_dir / "portfolio_candidates.json", data_dir / "portfolio_candidates_raw.json"]
        if not strict:
            cands_priority.extend([self.settings.lakehouse_dir / "portfolio_candidates.json", self.settings.lakehouse_dir / "portfolio_candidates_raw.json"])

        for p in cands_priority:
            if p.exists():
                try:
                    with open(p, "r") as f:
                        raw_data = json.load(f)
                    # Handle both list and dict formats (Phase 373)
                    if isinstance(raw_data, list):
                        result.raw_candidates = raw_data
                    elif isinstance(raw_data, dict):
                        result.raw_candidates = []
                        for sym, meta in raw_data.items():
                            if isinstance(meta, dict):
                                meta["symbol"] = sym
                                result.raw_candidates.append(meta)
                    break
                except Exception as e:
                    logger.warning(f"Failed to load candidates from {p}: {e}")

        # 2. Load Returns (Hybrid Loader)
        # Priority: Run Parquet -> Lakehouse Parquet
        returns_priority = [
            data_dir / "returns_matrix.parquet",
        ]
        if not strict:
            returns_priority.extend(
                [
                    self.settings.lakehouse_dir / "returns_matrix.parquet",
                    self.settings.lakehouse_dir / "portfolio_returns.parquet",
                ]
            )

        r_path = next((p for p in returns_priority if p.exists()), None)

        if r_path:
            result.returns = pd.read_parquet(r_path)
            result.returns = ensure_utc_index(result.returns)

        # 3. Load Features (Hybrid Loader)
        features_priority = [
            data_dir / "features_matrix.parquet",
        ]
        if not strict:
            features_priority.extend(
                [
                    self.settings.lakehouse_dir / "features_matrix.parquet",
                ]
            )

        f_path = next((p for p in features_priority if p.exists()), None)

        if f_path:
            try:
                result.features = pd.read_parquet(f_path)
                result.features = ensure_utc_index(result.features)
            except Exception as e:
                logger.warning(f"Failed to load features matrix: {e}")

        # 4. Load Metadata
        metadata_priority = [data_dir / "metadata_catalog.json", data_dir / "portfolio_meta.json"]
        if not strict:
            metadata_priority.extend([self.settings.lakehouse_dir / "metadata_catalog.json", self.settings.lakehouse_dir / "portfolio_meta.json"])

        metadata_path = next((p for p in metadata_priority if p.exists()), None)
        if metadata_path:
            with open(metadata_path, "r") as f:
                result.metadata = json.load(f)

        # 5. Load Stats
        stats_priority = [data_dir / "stats_matrix.parquet", data_dir / "antifragility_stats.json"]
        if not strict:
            stats_priority.extend([self.settings.lakehouse_dir / "stats_matrix.parquet", self.settings.lakehouse_dir / "antifragility_stats.json"])

        stats_path = next((p for p in stats_priority if p.exists()), None)
        if stats_path:
            if stats_path.suffix == ".parquet":
                result.stats = pd.read_parquet(stats_path)
            else:
                try:
                    result.stats = pd.read_json(stats_path)
                except Exception:
                    logger.warning(f"Failed to parse JSON stats at {stats_path}")

        return result
