from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingViewScraperSettings(BaseSettings):
    """Centralized, env-configurable paths for generated artifacts."""

    model_config = SettingsConfigDict(
        env_prefix="TV_",
        env_file=(".env",),
        extra="ignore",
        case_sensitive=False,
    )

    artifacts_dir: Path = Path("artifacts")
    lakehouse_dir: Path = Path("data/lakehouse")
    summaries_dir: Path | None = None

    # Use TV_RUN_ID to keep a single artifact run directory per workflow.
    run_id: str = Field(default_factory=lambda: os.getenv("TV_RUN_ID") or os.getenv("RUN_ID") or os.getenv("TV_EXPORT_RUN_ID") or datetime.now().strftime("%Y%m%d-%H%M%S"))

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
        """Create the per-run output dir (does not modify `latest`)."""

        run_dir = self.summaries_run_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def promote_summaries_latest(self) -> None:
        """Point `latest` at this run after successful finalize."""

        run_dir = self.prepare_summaries_run_dir()
        self._ensure_latest_symlink(run_dir)

    def _ensure_latest_symlink(self, run_dir: Path) -> None:
        latest = self.summaries_latest_link
        runs_rel_target = Path("runs") / self.run_id

        latest.parent.mkdir(parents=True, exist_ok=True)
        self.summaries_runs_dir.mkdir(parents=True, exist_ok=True)

        # If `latest` exists as a directory from an older layout, preserve it.
        if latest.exists() and not latest.is_symlink() and latest.is_dir():
            try:
                if any(latest.iterdir()):
                    backup_name = f"legacy_latest_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    latest.rename(self.summaries_runs_dir / backup_name)
                else:
                    latest.rmdir()
            except Exception:
                # Leave it in place rather than risking data loss.
                return

        if latest.is_symlink() or latest.exists():
            try:
                latest.unlink()
            except Exception:
                return

        try:
            latest.symlink_to(runs_rel_target, target_is_directory=True)
        except OSError:
            # Fallback for platforms/environments without symlink support:
            # mirror the run directory into a real `latest/` folder.
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
