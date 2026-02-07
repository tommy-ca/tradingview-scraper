from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

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

    def _resolve_path(self, filenames: List[str], search_dirs: List[Path]) -> Path | None:
        """
        Helper to find the first existing file from a list of filenames across search directories.
        """
        for d in search_dirs:
            for fname in filenames:
                p = d / fname
                if p.exists():
                    return p
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

        search_dirs = []
        if run_dir:
            search_dirs.append(run_dir / "data")

        # Fallback to lakehouse if no run found (legacy behavior) or if not strict
        if not run_dir or not strict:
            if self.settings.lakehouse_dir not in search_dirs:
                search_dirs.append(self.settings.lakehouse_dir)

        logger.info(f"Loading run data (run_dir={run_dir}, strict={strict})")

        result = RunData()

        # 1. Load Candidates
        cands_path = self._resolve_path(["portfolio_candidates.json", "portfolio_candidates_raw.json"], search_dirs)

        if cands_path:
            try:
                with open(cands_path, "r") as f:
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
            except Exception as e:
                logger.warning(f"Failed to load candidates from {cands_path}: {e}")

        # 2. Load Returns
        r_path = self._resolve_path(["returns_matrix.parquet", "portfolio_returns.parquet"], search_dirs)

        if not r_path:
            r_path = self._resolve_path(["returns_matrix.pkl", "portfolio_returns.pkl"], search_dirs)
            if r_path:
                logger.warning(f"Using deprecated pickle format for returns: {r_path}")
                r_path = self.ensure_safe_path(r_path)

        if r_path:
            try:
                if r_path.suffix == ".parquet":
                    df_ret = pd.read_parquet(r_path)
                elif r_path.suffix == ".pkl":
                    df_ret = pd.read_pickle(r_path)
                else:
                    df_ret = pd.DataFrame()  # Should not happen with current filenames

                # Type ignore: ensure_utc_index returns Union, but we know it's a DataFrame here
                result.returns = cast(pd.DataFrame, ensure_utc_index(df_ret))
            except Exception as e:
                logger.warning(f"Failed to load returns matrix from {r_path}: {e}")

        # 3. Load Features
        f_path = self._resolve_path(["features_matrix.parquet"], search_dirs)

        if not f_path:
            f_path = self._resolve_path(["features_matrix.pkl"], search_dirs)
            if f_path:
                logger.warning(f"Using deprecated pickle format for features: {f_path}")
                f_path = self.ensure_safe_path(f_path)

        if f_path:
            try:
                if f_path.suffix == ".parquet":
                    df_feat = pd.read_parquet(f_path)
                elif f_path.suffix == ".pkl":
                    df_feat = pd.read_pickle(f_path)
                else:
                    df_feat = pd.DataFrame()

                # Type ignore: ensure_utc_index returns Union, but we know it's a DataFrame here
                result.features = cast(pd.DataFrame, ensure_utc_index(df_feat))
            except Exception as e:
                logger.warning(f"Failed to load features matrix from {f_path}: {e}")

        # 4. Load Metadata
        m_path = self._resolve_path(["metadata_catalog.json", "portfolio_meta.json"], search_dirs)

        if m_path:
            try:
                with open(m_path, "r") as f:
                    result.metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")

        # 5. Load Stats
        s_path = self._resolve_path(["stats_matrix.parquet", "antifragility_stats.json"], search_dirs)

        if not s_path:
            s_path = self._resolve_path(["stats_matrix.pkl"], search_dirs)
            if s_path:
                logger.warning(f"Using deprecated pickle format for stats: {s_path}")
                s_path = self.ensure_safe_path(s_path)

        if s_path:
            if s_path.suffix == ".parquet":
                try:
                    result.stats = pd.read_parquet(s_path)
                except Exception as e:
                    logger.warning(f"Failed to load parquet stats: {e}")
            elif s_path.suffix == ".pkl":
                try:
                    result.stats = pd.read_pickle(s_path)
                except Exception as e:
                    logger.warning(f"Failed to load pickle stats: {e}")
            else:
                try:
                    result.stats = pd.read_json(s_path)
                except Exception:
                    logger.warning(f"Failed to parse JSON stats at {s_path}")

        return result
