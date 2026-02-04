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

    def _resolve_candidates_path(self, *, context: SelectionContext) -> str:
        settings = get_settings()
        strict_iso = os.getenv("TV_STRICT_ISOLATION") == "1"

        if self.candidates_path:
            return self.candidates_path

        run_data_dir = (settings.summaries_runs_dir / context.run_id / "data").resolve()
        run_sel = run_data_dir / "portfolio_candidates.json"
        run_raw = run_data_dir / "portfolio_candidates_raw.json"

        for p in [run_sel, run_raw]:
            if p.exists():
                return str(p)

        if strict_iso:
            raise FileNotFoundError(f"[STRICT ISOLATION] Candidates missing in run-dir: {run_sel.name} / {run_raw.name}")

        lake_sel = settings.lakehouse_dir / "portfolio_candidates.json"
        lake_raw = settings.lakehouse_dir / "portfolio_candidates_raw.json"
        for p in [lake_sel, lake_raw]:
            if p.exists():
                logger.warning("IngestionStage: falling back to lakehouse candidates at %s (run_id=%s).", p, context.run_id)
                return str(p)

        raise FileNotFoundError(f"Candidates manifest not found (run_id={context.run_id})")

    def _resolve_returns_path(self, *, context: SelectionContext) -> str:
        settings = get_settings()
        strict_iso = os.getenv("TV_STRICT_ISOLATION") == "1"

        if self.returns_path:
            return self.returns_path

        run_data_dir = (settings.summaries_runs_dir / context.run_id / "data").resolve()
        candidates = [
            run_data_dir / "returns_matrix.parquet",
            run_data_dir / "returns_matrix.pkl",
            run_data_dir / "returns_matrix.pickle",
        ]
        for p in candidates:
            if p.exists():
                return str(p)

        if strict_iso:
            raise FileNotFoundError(f"[STRICT ISOLATION] Returns matrix missing in run-dir (run_id={context.run_id})")

        lake_candidates = [
            settings.lakehouse_dir / "returns_matrix.parquet",
            settings.lakehouse_dir / "portfolio_returns.pkl",
            settings.lakehouse_dir / "portfolio_returns.parquet",
        ]
        for p in lake_candidates:
            if p.exists():
                logger.warning("IngestionStage: falling back to lakehouse returns at %s (run_id=%s).", p, context.run_id)
                return str(p)

        return ""

    def _resolve_features_path(self, *, context: SelectionContext) -> str:
        settings = get_settings()
        strict_iso = os.getenv("TV_STRICT_ISOLATION") == "1"

        run_data_dir = (settings.summaries_runs_dir / context.run_id / "data").resolve()
        run_feat = run_data_dir / "features_matrix.parquet"

        if run_feat.exists():
            return str(run_feat)

        if strict_iso:
            return ""

        lake_feat = settings.lakehouse_dir / "features_matrix.parquet"
        if lake_feat.exists():
            logger.warning("IngestionStage: falling back to lakehouse features at %s (run_id=%s).", lake_feat, context.run_id)
            return str(lake_feat)

        return ""

    def execute(self, context: SelectionContext) -> SelectionContext:
        candidates_path = self._resolve_candidates_path(context=context)
        returns_path = self._resolve_returns_path(context=context)
        features_path = self._resolve_features_path(context=context)

        logger.info("Executing Ingestion Stage (run_id=%s) candidates=%s returns=%s features=%s", context.run_id, candidates_path, returns_path, features_path)

        # 1. Load Candidates
        if not os.path.exists(candidates_path):
            raise FileNotFoundError(f"Candidates manifest not found: {candidates_path}")

        with open(candidates_path, "r") as f:
            raw_data = json.load(f)

        # Handle both list and dict formats
        if isinstance(raw_data, list):
            context.raw_pool = raw_data
        elif isinstance(raw_data, dict):
            # If it's a dict from portfolio_meta.json, convert to list of symbols with metadata
            context.raw_pool = []
            for sym, meta in raw_data.items():
                if isinstance(meta, dict):
                    meta["symbol"] = sym
                    context.raw_pool.append(meta)
        else:
            context.raw_pool = []

        # 2. Load Returns
        if not returns_path or not os.path.exists(returns_path):
            logger.warning("Returns matrix not found. Initializing empty (run_id=%s).", context.run_id)
            context.returns_df = pd.DataFrame()
        else:
            ext = os.path.splitext(returns_path)[1].lower()
            if ext == ".parquet":
                context.returns_df = pd.read_parquet(returns_path)
            elif ext in [".pkl", ".pickle"]:
                data = pd.read_pickle(returns_path)
                if isinstance(data, pd.Series):
                    context.returns_df = data.to_frame()
                else:
                    context.returns_df = data
            else:
                context.returns_df = pd.read_csv(returns_path, index_col=0, parse_dates=True)

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

        # 4. Load Features (Finding 056)
        if features_path and os.path.exists(features_path):
            try:
                logger.info("Loading features from %s", features_path)
                features_df = pd.read_parquet(features_path)
                context.feature_store = features_df

                # Determine alignment timestamp
                # Prefer the last timestamp in returns_df to ensure alignment
                alignment_dt = None
                if not context.returns_df.empty:
                    alignment_dt = context.returns_df.index[-1]

                # Extract the slice
                if alignment_dt is not None and alignment_dt in features_df.index:
                    current_features = features_df.loc[alignment_dt]
                else:
                    if alignment_dt is not None:
                        logger.warning("Features matrix missing timestamp %s. Using last available.", alignment_dt)
                    current_features = features_df.iloc[-1]

                merged_count = 0
                for candidate in context.raw_pool:
                    sym = candidate.get("symbol")
                    if not sym:
                        continue

                    # Known features to merge
                    for feat in ["recommend_all", "recommend_ma", "recommend_other"]:
                        if (sym, feat) in current_features.index:
                            val = current_features[(sym, feat)]
                            if pd.notna(val):
                                candidate[feat] = float(val)
                                merged_count += 1

                logger.info("Merged %d feature points into candidates pool.", merged_count)

            except Exception as e:
                logger.error("Failed to load/merge features matrix: %s", e)
                # We don't raise here unless STRICT, but keeping it robust for now
                if strict:
                    raise

        context.log_event(self.name, "DataLoaded", {"n_candidates": len(context.raw_pool), "returns_shape": context.returns_df.shape, "n_dropped": len(failed_symbols)})

        return context
