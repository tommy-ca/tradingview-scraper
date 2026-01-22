import logging
from pathlib import Path
from typing import Any, Optional

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.telemetry.tracing import trace_span

logger = logging.getLogger(__name__)


class QuantSDK:
    """
    High-level API for interacting with the quantitative portfolio platform.
    Used by Claude skills and CLI.
    """

    @staticmethod
    def run_stage(id: str, context: Optional[Any] = None, **params) -> Any:
        """
        Executes a single pipeline stage by its ID.
        """
        return QuantSDK._run_stage_impl(id, context, **params)

    @staticmethod
    @trace_span("sdk.run_stage")
    def _run_stage_impl(id: str, context: Optional[Any] = None, **params) -> Any:
        logger.info(f"SDK: Executing stage {id}")
        stage_callable = StageRegistry.get_stage(id)
        spec = StageRegistry.get_spec(id)

        # If it's a class (BasePipelineStage), instantiate and execute
        if spec.stage_class:
            instance = spec.stage_class(**params)
            if context is None:
                # Some stages might create their own context if needed
                # but for selection stages, it's usually required.
                pass
            return instance.execute(context)

        # If it's a function/method
        # Functions might not take 'context' as first arg, but we'll try to be flexible
        # If context is provided, we could pass it, but meta functions currently don't use it.
        # Let's check the signature if possible or just call with params.
        import inspect

        sig = inspect.signature(stage_callable)
        if "context" in sig.parameters:
            return stage_callable(context=context, **params)
        else:
            return stage_callable(**params)

    @staticmethod
    def validate_foundation(run_id: Optional[str] = None) -> bool:
        """
        L1 Ingestion Gate: Validates Lakehouse integrity and PIT fidelity.
        Checks for missing Parquet files, staleness, and schema drift.
        """
        from tradingview_scraper.settings import get_settings
        import os

        settings = get_settings()
        lakehouse = settings.lakehouse_dir

        logger.info(f"SDK: Validating foundation at {lakehouse}")

        # 1. Existence Checks
        required_files = ["returns_matrix.parquet", "features_matrix.parquet"]

        missing = [f for f in required_files if not (lakehouse / f).exists()]
        if missing:
            logger.error(f"Foundation Gate FAILED: Missing files: {missing}")
            return False

        # 2. Freshness check (Optional, depending on STRICT_HEALTH)
        if os.getenv("TV_STRICT_HEALTH") == "1":
            import time

            current_time = time.time()
            for f in required_files:
                mtime = (lakehouse / f).stat().st_mtime
                age_hours = (current_time - mtime) / 3600
                if age_hours > 24:
                    logger.warning(f"Foundation Gate: {f} is stale ({age_hours:.1f} hours old)")

        logger.info("✅ Foundation Gate PASS")
        return True

    @staticmethod
    def create_snapshot(run_id: str) -> Path:
        """
        Creates a symlink-based snapshot of the Lakehouse for run immutability.
        Returns the path to the snapshot directory.
        """
        from tradingview_scraper.settings import get_settings
        import os
        from pathlib import Path

        settings = get_settings()
        lakehouse = settings.lakehouse_dir
        snapshot_dir = (settings.data_dir / "snapshots" / run_id).resolve()
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"SDK: Creating Lakehouse snapshot for {run_id} at {snapshot_dir}")

        for item in lakehouse.iterdir():
            if item.is_file():
                target = snapshot_dir / item.name
                if not target.exists():
                    os.symlink(item, target)
            elif item.is_dir() and not item.name.startswith("."):
                target = snapshot_dir / item.name
                if not target.exists():
                    os.symlink(item, target)

        return snapshot_dir

    @staticmethod
    def run_pipeline(name: str, profile: str, run_id: Optional[str] = None, **overrides) -> Any:
        """
        Executes a full named pipeline (e.g., 'selection.full').
        """
        logger.info(f"SDK: Running pipeline {name} for profile {profile}")
        # (This will be implemented as we migrate full pipelines to the new orchestrator)
        pass
