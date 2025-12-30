from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple, Type

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)


class ManifestSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source to load from a multi-profile JSON manifest."""

    def __init__(self, settings_cls: Type[BaseSettings], manifest_path: Path, profile_name: str):
        super().__init__(settings_cls)
        self.manifest_path = manifest_path
        self.profile_name = profile_name

    def get_field_value(self, field: Any, field_name: str) -> Tuple[Any, str, bool]:
        # Not used for this combined source
        return None, field_name, False

    def __call__(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            return {}

        try:
            with open(self.manifest_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.debug(f"Manifest not found: {self.manifest_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse manifest {self.manifest_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading manifest: {e}")
            return {}

        profiles = data.get("profiles", {})
        # If profile_name is not provided or not in manifest, use default_profile
        active_profile = self.profile_name or data.get("default_profile", "production")

        profile_data = profiles.get(active_profile)
        if not profile_data:
            return {}

        # Flatten nested JSON into flat keys for BaseSettings
        flattened = {}
        for section in ["data", "selection", "risk", "backtest", "tournament", "discovery"]:
            if section in profile_data:
                if section == "discovery":
                    # Keep discovery structured for specialized consumption
                    flattened["discovery"] = profile_data[section]
                else:
                    for k, v in profile_data[section].items():
                        flattened[k] = v

        # Merge env block
        if "env" in profile_data:
            for k, v in profile_data["env"].items():
                flattened[k.lower()] = v

        return flattened


class TradingViewScraperSettings(BaseSettings):
    """Centralized, env-configurable paths and workflow parameters."""

    model_config = SettingsConfigDict(
        env_prefix="TV_",
        env_file=(".env",),
        extra="ignore",
        case_sensitive=False,
    )

    # Infrastructure
    artifacts_dir: Path = Path("artifacts")
    lakehouse_dir: Path = Path("data/lakehouse")
    summaries_dir: Path | None = None
    manifest_path: Path = Path("configs/manifest.json")
    profile: str = Field(default_factory=lambda: os.getenv("TV_PROFILE") or "")

    # Discovery & Prep
    batch_size: int = 5
    lookback_days: int = 200
    backfill: bool = True
    gapfill: bool = True
    max_symbols: int = 200

    # Selection Logic
    top_n: int = 3
    threshold: float = 0.4

    # Optimization
    cluster_cap: float = 0.25

    # Backtest
    train_window: int = 120
    test_window: int = 20
    step_size: int = 20
    backtest_simulator: str = "custom"
    backtest_slippage: float = 0.0005  # 5 bps
    backtest_commission: float = 0.0001  # 1 bp
    backtest_cash_asset: str = "USDT"

    # Tournament
    tournament_engines: str = "custom,skfolio,riskfolio,pyportfolioopt,cvxportfolio"
    tournament_profiles: str = "min_variance,hrp,max_sharpe,barbell"

    # Discovery (Structured)
    discovery: Dict[str, Any] = Field(default_factory=dict)

    # Environment overrides (GIST_ID, etc.)
    gist_id: str = "e888e1eab0b86447c90c26e92ec4dc36"
    meta_refresh: str = "0"
    meta_audit: str = "0"

    # Runtime run_id logic
    run_id: str = Field(default_factory=lambda: os.getenv("TV_RUN_ID") or os.getenv("RUN_ID") or os.getenv("TV_EXPORT_RUN_ID") or datetime.now().strftime("%Y%m%d-%H%M%S"))

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        # Determine manifest path and profile before creating the source
        # We look in env vars first since Pydantic hasn't finished loading yet
        m_path = Path(os.getenv("TV_MANIFEST_PATH") or "configs/manifest.json")
        p_name = os.getenv("TV_PROFILE") or ""

        return (
            init_settings,
            env_settings,
            ManifestSettingsSource(settings_cls, m_path, p_name),
            dotenv_settings,
        )

    def get_discovery_config(self, scanner_type: str) -> Dict[str, Any]:
        """Extracts the discovery configuration for a specific scanner type."""
        return self.discovery.get(scanner_type, {})

    @property
    def summaries_root_dir(self) -> Path:
        return self.summaries_dir or (self.artifacts_dir / "summaries")

    @property
    def summaries_runs_dir(self) -> Path:
        return self.summaries_root_dir / "runs"

    @property
    def summaries_run_dir(self) -> Path:
        return self.summaries_runs_dir / self.run_id

    @property
    def summaries_latest_link(self) -> Path:
        return self.summaries_root_dir / "latest"

    def prepare_summaries_run_dir(self) -> Path:
        run_dir = self.summaries_run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def promote_summaries_latest(self) -> None:
        run_dir = self.prepare_summaries_run_dir()
        self._ensure_latest_symlink(run_dir)

    def _ensure_latest_symlink(self, run_dir: Path) -> None:
        latest = self.summaries_latest_link
        runs_rel_target = Path("runs") / self.run_id

        latest.parent.mkdir(parents=True, exist_ok=True)
        self.summaries_runs_dir.mkdir(parents=True, exist_ok=True)

        if latest.exists() and not latest.is_symlink() and latest.is_dir():
            try:
                if any(latest.iterdir()):
                    backup_name = f"legacy_latest_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    latest.rename(self.summaries_runs_dir / backup_name)
                else:
                    latest.rmdir()
            except Exception:
                return

        if latest.is_symlink() or latest.exists():
            try:
                latest.unlink()
            except Exception:
                return

        try:
            latest.symlink_to(runs_rel_target, target_is_directory=True)
        except OSError:
            import shutil

            if latest.exists():
                try:
                    if latest.is_file() or latest.is_symlink():
                        latest.unlink()
                    else:
                        shutil.rmtree(latest)
                except Exception:
                    return

            try:
                shutil.copytree(run_dir, latest)
                (latest / "LATEST").write_text(self.run_id + "\n", encoding="utf-8")
            except Exception:
                return


@lru_cache
def get_settings() -> TradingViewScraperSettings:
    return TradingViewScraperSettings()


if __name__ == "__main__":
    # Helper for Makefile/CLI to export variables from the manifest
    settings = get_settings()
    if "--export-env" in sys.argv:
        # Map pydantic field names to institutional ENV names
        mapping = {
            "lookback_days": "LOOKBACK",
            "batch_size": "BATCH",
            "backfill": "BACKFILL",
            "gapfill": "GAPFILL",
            "top_n": "TOP_N",
            "threshold": "THRESHOLD",
            "cluster_cap": "CLUSTER_CAP",
            "train_window": "BACKTEST_TRAIN",
            "test_window": "BACKTEST_TEST",
            "step_size": "BACKTEST_STEP",
            "backtest_simulator": "BACKTEST_SIMULATOR",
            "backtest_slippage": "BACKTEST_SLIPPAGE",
            "backtest_commission": "BACKTEST_COMMISSION",
            "backtest_cash_asset": "BACKTEST_CASH_ASSET",
            "tournament_engines": "TOURNAMENT_ENGINES",
            "tournament_profiles": "TOURNAMENT_PROFILES",
            "gist_id": "GIST_ID",
            "meta_refresh": "META_REFRESH",
            "meta_audit": "META_AUDIT",
        }
        for field, env_name in mapping.items():
            val = getattr(settings, field)
            if isinstance(val, bool):
                val = "1" if val else "0"
            print(f"export {env_name}={val}")
