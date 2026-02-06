import json
import logging
import os

import pandas as pd

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.settings import get_settings

logger = logging.getLogger("pipelines.selection.ingestion")


@StageRegistry.register(id="foundation.ingest", name="Ingestion", description="Loads raw candidates and return data", category="foundation")
class IngestionStage(BasePipelineStage):
    """
    Stage 1: Multi-Sleeve Ingestion.
    Loads raw candidates and return data from the Lakehouse.
    """

    @property
    def name(self) -> str:
        return "Ingestion"

    def __init__(self, candidates_path: str | None = None, returns_path: str | None = None):
        # If explicit paths are provided, we honor them. Otherwise resolve at execute-time
        # using the SelectionContext.run_id to prefer run-dir isolation (Phase 373).
        self.candidates_path = candidates_path
        self.returns_path = returns_path

    def execute(self, context: SelectionContext) -> SelectionContext:
        from tradingview_scraper.data.loader import DataLoader

        settings = get_settings()
        strict = os.getenv("TV_STRICT_ISOLATION") == "1"
        loader = DataLoader(settings)

        # 1. Validate Run ID (Defense in Depth)
        context.validate_run_id(context.run_id)

        # 2. Resolve and Anchor Paths
        run_dir = loader.ensure_safe_path(settings.summaries_runs_dir / context.run_id)
        logger.info("Executing Ingestion Stage (run_id=%s) strict=%s", context.run_id, strict)

        # Use the centralized DataLoader for consistent loading logic (Phase 373)
        try:
            if self.candidates_path or self.returns_path:
                # Manual overrides
                if self.candidates_path:
                    safe_cands = loader.ensure_safe_path(self.candidates_path)
                    if safe_cands.exists():
                        with open(safe_cands, "r") as f:
                            raw_data = json.load(f)
                            if isinstance(raw_data, list):
                                context.raw_pool = raw_data
                            elif isinstance(raw_data, dict):
                                context.raw_pool = [{"symbol": k, **v} if isinstance(v, dict) else {"symbol": k} for k, v in raw_data.items()]

                if self.returns_path:
                    safe_rets = loader.ensure_safe_path(self.returns_path)
                    if safe_rets.exists():
                        context.returns_df = pd.read_parquet(safe_rets) if str(safe_rets).endswith(".parquet") else pd.read_csv(safe_rets, index_col=0, parse_dates=True)
            else:
                run_data = loader.load_run_data(run_dir=run_dir, strict=strict)
                context.raw_pool = run_data["raw_candidates"]
                context.returns_df = run_data["returns"]
        except FileNotFoundError as e:
            if strict:
                raise
            logger.warning(f"IngestionStage: {e}. Initializing empty.")
            context.raw_pool = []
            context.returns_df = pd.DataFrame()

        # 3. L1 Data Contract Validation
        from tradingview_scraper.pipelines.selection.base import IngestionValidator

        strict = os.getenv("TV_STRICT_HEALTH") == "1"
        failed_symbols = IngestionValidator.validate_returns(context.returns_df, strict=strict)

        if failed_symbols:
            logger.warning("IngestionValidator: Dropping %d symbols that failed data contracts.", len(failed_symbols))
            context.returns_df = context.returns_df.drop(columns=failed_symbols)
            if strict:
                logger.error("STRICT MODE: Failing pipeline due to data contract violations: %s", failed_symbols)
                raise RuntimeError(f"Data Contract Violation: {failed_symbols}")

        context.log_event(self.name, "DataLoaded", {"n_candidates": len(context.raw_pool), "returns_shape": context.returns_df.shape, "n_dropped": len(failed_symbols)})

        return context
