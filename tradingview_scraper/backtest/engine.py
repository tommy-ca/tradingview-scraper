from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

import pandas as pd

from tradingview_scraper.backtest.models import NumericalWorkspace
from tradingview_scraper.backtest.orchestration import WalkForwardOrchestrator, WalkForwardWindow
from tradingview_scraper.backtest.strategies import StrategyFactory
from tradingview_scraper.data.loader import DataLoader, RunData
from tradingview_scraper.portfolio_engines import EngineRequest, ProfileName, build_engine, build_simulator
from tradingview_scraper.settings import TradingViewScraperSettings, get_settings
from tradingview_scraper.utils.audit import AuditLedger
from tradingview_scraper.utils.synthesis import StrategySynthesizer
from tradingview_scraper.regime import MarketRegimeDetector

from tradingview_scraper.pipelines.allocation.base import AllocationContext
from tradingview_scraper.pipelines.allocation.pipeline import AllocationPipeline
from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.pipeline import SelectionPipeline

try:
    from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader
except ImportError:
    PersistentDataLoader = None

logger = logging.getLogger(__name__)


def persist_tournament_artifacts(results: dict[str, Any], output_dir: Path) -> None:
    """
    Saves tournament results and high-level metadata to structured CSV and JSON files.

    Args:
        results: Dictionary containing results list and metadata.
        output_dir: Root directory for artifact storage.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results["results"]).to_csv(output_dir / "tournament_results.csv", index=False)
    with open(output_dir / "tournament_meta.json", "w") as f:
        json.dump(results["meta"], f, indent=2)


class BacktestEngine:
    """
    Institutional Backtest Orchestrator.
    Manages the lifecycle of a walk-forward tournament.
    (Pillar 3 Compliance: Stateful Orchestration).
    """

    def __init__(self, settings: TradingViewScraperSettings | None = None):
        self.settings = settings or get_settings()
        self.loader = DataLoader(self.settings)
        self.synthesizer = StrategySynthesizer()

        self.returns = pd.DataFrame()
        self.features_matrix = pd.DataFrame()
        self.metadata = {}
        self.stats = pd.DataFrame()
        self.raw_candidates: list[dict[str, Any]] = []

        # State Accumulators for the active run
        self.results: list[dict[str, Any]] = []
        self.return_series: dict[str, list[pd.Series]] = {}
        self.current_holdings: dict[str, Any] = {}
        self.ledger: AuditLedger | None = None

        # JIT Numerical Workspace
        self.workspace: NumericalWorkspace | None = None

        # Components
        self.detector = MarketRegimeDetector(enable_audit_log=False)
        self.selection_pipeline = SelectionPipeline(run_id=getattr(self.settings, "run_id", "backtest_v4"))
        self.allocation_pipeline = AllocationPipeline()

        # MTF Ingestion
        self.mtf_loader = None

    def load_data(self, run_dir: Path | None = None) -> None:
        """
        Loads returns and metadata from the institutional DataLoader.

        Args:
            run_dir: Optional path to a specific run directory.

        Audit:
            - Security: Validates path boundaries via DataLoader.
            - Integrity: Ensures UTC DatetimeIndex on all loaded matrices.
        """
        data: RunData = self.loader.load_run_data(run_dir)
        self.returns = data.returns
        self.features_matrix = data.features
        self.metadata = data.metadata
        self.stats = data.stats
        self.raw_candidates = data.raw_candidates

    def run_tournament(
        self,
        mode: str = "production",
        train_window: int | None = None,
        test_window: int | None = None,
        step_size: int | None = None,
        run_dir: Path | None = None,
        lightweight: bool = False,
    ) -> dict[str, Any]:
        """
        Runs a rolling-window backtest tournament.
        (Pillar 3 Standard: Zero Look-Ahead).
        """
        if self.returns.empty:
            self.load_data(run_dir=run_dir)

        is_meta = self._is_meta_profile(self.settings.profile or "")

        resolved_train = int(train_window or self.settings.train_window)
        resolved_test = int(test_window or self.settings.test_window)
        resolved_step = int(step_size or self.settings.step_size)

        if is_meta:
            if not self._prepare_meta_returns(self.settings, run_dir):
                return {"results": [], "meta": {}}

        # Initialize Workspace
        self.workspace = NumericalWorkspace.for_dimensions(resolved_train, len(self.returns.columns))

        # Tournament configuration
        if lightweight:
            profiles = ["hrp"]
            engines = ["custom"]
            sim_names = ["vectorbt"]
        else:
            profiles = self.settings.profiles.split(",")
            engines = self.settings.engines.split(",")
            sim_names = self.settings.backtest_simulators.split(",")

        self.results = []
        self.return_series = {}
        self.current_holdings = {}

        results_meta = {
            "mode": mode,
            "train_window": resolved_train,
            "test_window": resolved_test,
            "step_size": resolved_step,
            "profiles": profiles,
            "engines": engines,
            "simulators": sim_names,
            "lightweight": lightweight,
        }

        if not run_dir:
            run_dir = self.settings.prepare_summaries_run_dir()

        self.ledger = AuditLedger(run_dir)

        orchestrator = WalkForwardOrchestrator(
            train_window=resolved_train,
            test_window=resolved_test,
            step_size=resolved_step,
        )

        windows = list(orchestrator.generate_windows(self.returns))
        logger.info(f"Tournament Started: {len(self.returns)} rows available. Windows: {len(windows)}")

        for window in windows:
            self._run_window_step(window, orchestrator, is_meta, profiles, engines, sim_names)

        self._save_artifacts(run_dir)

        final_series_map = {}
        for key, series_list in self.return_series.items():
            if series_list:
                s_raw = pd.concat(series_list)
                s_series = s_raw if isinstance(s_raw, pd.Series) else pd.Series(s_raw)
                final_series_map[key] = s_series.sort_index()

        return {"results": self.results, "meta": results_meta, "stitched_returns": final_series_map}

    def _run_window_step(
        self,
        window: WalkForwardWindow,
        orchestrator: WalkForwardOrchestrator,
        is_meta: bool,
        profiles: list[str],
        engines: list[str],
        sim_names: list[str],
    ) -> None:
        """Executes the 3-pillar sequence for a single rolling window."""
        current_date = window.test_dates[0]
        train_rets, test_rets = orchestrator.slice_data(self.returns, window)

        # 2. Regime Detection
        regime_name, quadrant_name = self._detect_market_regime(train_rets, workspace=self.workspace)
        market_env = quadrant_name  # In new regime model, quadrant is the market env

        # 3. Pillar 1: Universe Selection (MLOps v4 Pipeline)
        selection_ctx = self.selection_pipeline.run_with_data(
            returns_df=train_rets,
            raw_candidates=self.raw_candidates,
            overrides={
                "top_n": self.settings.top_n,
                "threshold": self.settings.threshold,
            },
        )

        if not selection_ctx.winners:
            return

        # Integrity Check: Filter winners missing from returns matrix
        winners = [w for w in selection_ctx.winners if w["symbol"] in train_rets.columns]
        if not winners:
            return

        # Merge winner metadata into local state
        for w in winners:
            self.metadata[w["symbol"]] = w

        # MTF Ingestion Trigger
        if self.settings.timeframes:
            self._fetch_mtf_for_candidates(winners)

        if self.ledger:
            self._record_selection_audit(winners, train_rets, window.step_index, selection_ctx)

        # 4. Pillar 2: Strategy Synthesis
        train_rets_strat = self._execute_synthesis(train_rets, winners, is_meta, workspace=self.workspace)

        # 5. Pillar 3: Allocation & Simulation (Pillar 3 Pipeline)
        alloc_ctx = AllocationContext(
            run_id=getattr(self.ledger, "run_id", "backtest"),
            window=window,
            regime_name=regime_name,
            market_env=market_env,
            train_rets=train_rets,
            train_rets_strat=train_rets_strat,
            test_rets=test_rets,
            bench_rets=cast(pd.Series, train_rets[self.settings.benchmark_symbols[0]]) if self.settings.benchmark_symbols and self.settings.benchmark_symbols[0] in train_rets.columns else None,
            clusters={},  # Pipeline will fill this
            window_meta={s: self.metadata.get(s, {}) for s in train_rets_strat.columns},
            composition_map=self.synthesizer.composition_map,
            stats=self.stats,
            is_meta=is_meta,
            engine_names=engines,
            profiles=profiles,
            sim_names=sim_names,
            results=self.results,
            current_holdings=self.current_holdings,
            return_series=self.return_series,
            ledger=self.ledger,
        )

        self.allocation_pipeline.run(alloc_ctx)

    def _fetch_mtf_for_candidates(self, winners: list[dict[str, Any]]) -> None:
        """Triggers Multi-Timeframe ingestion for winning candidates."""
        if not self.settings.timeframes:
            return

        logger.info(f"Fetching MTF data for {len(winners)} candidates: {self.settings.timeframes}")

        try:
            # Use IngestionService for optimized parallel fetching
            # Deferred import to avoid circular dependencies with scripts
            from scripts.services.ingest_data import IngestionService

            service = IngestionService(lakehouse_dir=self.settings.lakehouse_dir)
            candidates = [w["symbol"] for w in winners]
            service.fetch_mtf_for_candidates(candidates, self.settings.timeframes)

        except (ImportError, ModuleNotFoundError):
            # Fallback to serial PersistentDataLoader if scripts module not available
            if PersistentDataLoader is None:
                logger.warning("IngestionService and PersistentDataLoader not available. Skipping MTF.")
                return

            if self.mtf_loader is None:
                self.mtf_loader = PersistentDataLoader(lakehouse_path=self.settings.lakehouse_dir)

            for w in winners:
                symbol = w["symbol"]
                for tf in self.settings.timeframes:
                    try:
                        # Sync with 1000 candle depth to ensure sufficient history for indicators
                        self.mtf_loader.sync(symbol, interval=tf, depth=1000)
                    except Exception as e:
                        logger.error(f"Failed to fetch MTF {tf} for {symbol}: {e}")

    def _execute_synthesis(
        self,
        train_rets: pd.DataFrame,
        winners: list[dict[str, Any]],
        is_meta: bool,
        workspace: NumericalWorkspace | None = None,
    ) -> pd.DataFrame:
        """Orchestrates Pillar 2: Strategy Synthesis."""
        if is_meta:
            winners_syms = [w["symbol"] for w in winners]
            return cast(pd.DataFrame, train_rets[winners_syms])

        return self.synthesizer.synthesize(train_rets, winners, self.settings.features, workspace=workspace)

    def _is_meta_profile(self, profile_name: str) -> bool:
        manifest_path = self.settings.manifest_path
        if not manifest_path.exists():
            return False
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        return "sleeves" in manifest.get("profiles", {}).get(profile_name, {})

    def _prepare_meta_returns(self, config: TradingViewScraperSettings, run_dir: Path | None) -> bool:
        """Establishes meta-returns matrix for fractal backtesting recursive simulation."""
        logger.info(f"🚀 RECURSIVE META-BACKTEST DETECTED: {config.profile}")

        if not run_dir:
            run_dir = self.settings.prepare_summaries_run_dir()

        anchor_prof = "hrp"
        temp_meta_path = run_dir / "data" / f"meta_returns_{config.profile}_{anchor_prof}.parquet"

        # Deferred import to avoid circular dependency
        from tradingview_scraper.utils.meta_returns import build_meta_returns

        build_meta_returns(
            meta_profile=config.profile,
            output_path=str(run_dir / "data" / "meta.parquet"),
            profiles=[anchor_prof],
            manifest_path=config.manifest_path,
            base_dir=run_dir / "data",
        )

        if temp_meta_path.exists():
            data = pd.read_parquet(temp_meta_path)
            if isinstance(data, pd.Series):
                self.returns = data.to_frame()
            else:
                self.returns = cast(pd.DataFrame, data)

            logger.info(f"Meta-Returns Matrix established: {self.returns.shape}")
            self.raw_candidates = [{"symbol": sid, "id": sid} for sid in self.returns.columns]
            return True
        else:
            logger.error(f"Failed to build meta-returns matrix at {temp_meta_path}. Aborting.")
            return False

    def _detect_market_regime(self, train_rets: pd.DataFrame, workspace: NumericalWorkspace | None = None) -> tuple[str, str]:
        if not train_rets.empty and len(train_rets) > 60:
            regime, _, quadrant = self.detector.detect_regime(train_rets, workspace=workspace)
            return regime, quadrant
        return "NORMAL", "NORMAL"

    def _record_selection_audit(self, winners: list[dict[str, Any]], train_rets: pd.DataFrame, window_index: int, context: SelectionContext):
        if self.ledger:
            winners_syms = [w["symbol"] for w in winners]
            alpha_scores = context.inference_outputs["alpha_score"].to_dict() if not context.inference_outputs.empty else {}

            metrics_payload = {
                "n_universe_symbols": len(self.returns.columns),
                "n_refinement_candidates": len(train_rets.columns),
                "n_winners": len(winners_syms),
                "winners": winners_syms,
                "alpha_scores": alpha_scores,
                "pipeline_audit": context.audit_trail,
            }
            self.ledger.record_outcome(
                step="backtest_select",
                status="success",
                output_hashes={},
                metrics=metrics_payload,
                data={
                    "relaxation_stage": context.params.get("relaxation_stage", 1),
                    "winners_meta": winners,
                },
                context={"window_index": window_index, "engine": "SelectionPipelineV4"},
            )

    def _save_artifacts(self, run_dir: Path) -> None:
        """
        Persists stitched return series and profile aliases to disk.
        (Standard: Parquet format for institutional auditability).
        """
        returns_out = run_dir / "data" / "returns"
        returns_out.mkdir(parents=True, exist_ok=True)
        for key, series_list in self.return_series.items():
            if series_list:
                full_series_raw = pd.concat(series_list)
                # Ensure it's a Series for LSP and runtime stability
                full_series = full_series_raw if isinstance(full_series_raw, pd.Series) else pd.Series(full_series_raw)
                full_series = full_series[~full_series.index.duplicated()].sort_index()
                # Transition to Parquet
                out_path = returns_out / f"{key}.parquet"
                full_series.to_frame(name="returns").to_parquet(out_path)

                # Alias for easier access
                parts = key.split("_")
                if len(parts) >= 3:
                    prof_name = "_".join(parts[2:])
                    alias_path = returns_out / f"{prof_name}.parquet"
                    if not alias_path.exists():
                        full_series.to_frame(name="returns").to_parquet(alias_path)
