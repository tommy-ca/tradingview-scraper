from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast

import pandas as pd

from tradingview_scraper.backtest.models import NumericalWorkspace, SimulationContext
from tradingview_scraper.backtest.orchestration import WalkForwardOrchestrator, WalkForwardWindow
from tradingview_scraper.backtest.strategies import StrategyFactory
from tradingview_scraper.data.loader import DataLoader
from tradingview_scraper.portfolio_engines import EngineRequest, ProfileName, build_engine, build_simulator
from tradingview_scraper.selection_engines import build_selection_engine, get_hierarchical_clusters
from tradingview_scraper.selection_engines.base import SelectionRequest, SelectionResponse
from tradingview_scraper.settings import TradingViewScraperSettings, get_settings
from tradingview_scraper.utils.audit import AuditLedger
from tradingview_scraper.utils.synthesis import StrategySynthesizer

logger = logging.getLogger(__name__)


def persist_tournament_artifacts(results: dict[str, Any], output_dir: Path):
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
        from tradingview_scraper.regime import MarketRegimeDetector

        self.detector = MarketRegimeDetector(enable_audit_log=False)

    def load_data(self, run_dir: Path | None = None) -> None:
        """
        Loads returns and metadata from the institutional DataLoader.

        Args:
            run_dir: Optional path to a specific run directory.

        Audit:
            - Security: Validates path boundaries via DataLoader.
            - Integrity: Ensures UTC DatetimeIndex on all loaded matrices.
        """
        data = self.loader.load_run_data(run_dir)
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

        final_series_map = {key: cast(pd.Series, pd.concat(series_list)).sort_index() for key, series_list in self.return_series.items() if series_list}
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

        # 3. Pillar 1: Universe Selection
        selection = self._execute_selection(train_rets, window.step_index)
        if not selection:
            return

        # 4. Pillar 2: Strategy Synthesis
        train_rets_strat = self._execute_synthesis(train_rets, selection.winners, is_meta, workspace=self.workspace)

        # 5. Pillar 3: Allocation & Simulation
        self._execute_allocation(
            window=window,
            regime_name=regime_name,
            market_env=market_env,
            train_rets=train_rets,
            train_rets_strat=train_rets_strat,
            selection=selection,
            profiles=profiles,
            engines=engines,
            sim_names=sim_names,
            is_meta=is_meta,
            test_rets=test_rets,
        )

    def _execute_selection(self, train_rets: pd.DataFrame, window_index: int) -> SelectionResponse | None:
        """Orchestrates Pillar 1: Universe Selection."""
        strategy = StrategyFactory.infer_strategy(self.settings.profile or "", self.settings.strategy)
        selection_engine = build_selection_engine(self.settings.features.selection_mode)

        req_select = SelectionRequest(
            top_n=self.settings.top_n,
            threshold=self.settings.threshold,
            strategy=strategy,
        )
        selection = selection_engine.select(
            returns=train_rets,
            raw_candidates=self.raw_candidates,
            stats_df=self.stats,
            request=req_select,
            workspace=self.workspace,
        )

        # Integrity Check: Filter winners missing from returns matrix
        if selection.winners:
            winners = [w for w in selection.winners if w["symbol"] in train_rets.columns]
            object.__setattr__(selection, "winners", winners)

        if not selection.winners:
            return None

        winners_syms = [w["symbol"] for w in selection.winners]

        # Merge winner metadata into local state
        for w in selection.winners:
            self.metadata[w["symbol"]] = w

        if self.ledger:
            self._record_selection_audit(selection, winners_syms, train_rets, selection_engine.name, window_index)

        return selection

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

    def _execute_allocation(
        self,
        window: WalkForwardWindow,
        regime_name: str,
        market_env: str,
        train_rets: pd.DataFrame,
        train_rets_strat: pd.DataFrame,
        selection: SelectionResponse,
        profiles: list[str],
        engines: list[str],
        sim_names: list[str],
        is_meta: bool,
        test_rets: pd.DataFrame,
    ) -> None:
        """Orchestrates Pillar 3: Portfolio Allocation & Simulation."""
        new_cluster_ids, _ = get_hierarchical_clusters(train_rets_strat, float(self.settings.threshold), 25)
        stringified_clusters = {}
        for sym, c_id in zip(train_rets_strat.columns, new_cluster_ids):
            stringified_clusters.setdefault(str(c_id), []).append(str(sym))

        bench_sym = self.settings.benchmark_symbols[0] if self.settings.benchmark_symbols else None
        bench_rets = cast(pd.Series, train_rets[bench_sym]) if bench_sym and bench_sym in train_rets.columns else None

        # Snapshot metadata for this cross-section
        window_meta = {s: self.metadata.get(s, {}) for s in train_rets_strat.columns}

        for engine_name in engines:
            profiles_to_run = ["adaptive"] if engine_name == "adaptive" else profiles
            for profile in profiles_to_run:
                ctx = SimulationContext(
                    engine_name=engine_name,
                    profile=profile,
                    window=window,
                    regime_name=regime_name,
                    market_env=market_env,
                    train_rets=train_rets,
                    train_rets_strat=train_rets_strat,
                    clusters=stringified_clusters,
                    window_meta=window_meta,
                    bench_rets=bench_rets,
                    is_meta=is_meta,
                    test_rets=test_rets,
                )
                self._process_optimization_window(ctx, sim_names)

    def _process_optimization_window(self, ctx: SimulationContext, sim_names: list[str]) -> None:
        """
        Processes optimization and simulation for a single window.

        Args:
            ctx: Full simulation context for the current window.
            sim_names: Simulators to execute after optimization.

        Audit:
            - Numerical Purity: Solvers are hardened strictly via decorators.
            - Fallback: Defaults to Equal Weight if solver fails even with hardening.
        """
        actual_profile = cast(ProfileName, ctx.profile)
        target_engine = ctx.engine_name
        if actual_profile in ["market", "benchmark"]:
            target_engine = "market"
        elif actual_profile == "barbell":
            target_engine = "custom"

        opt_ctx = {
            "window_index": ctx.window.step_index,
            "engine": target_engine,
            "profile": ctx.profile,
            "regime": ctx.regime_name,
            "actual_profile": actual_profile,
        }

        try:
            solver = build_engine(target_engine)
            if self.ledger:
                self.ledger.record_intent("backtest_optimize", opt_ctx, input_hashes={})

            req = EngineRequest(
                profile=actual_profile,
                engine=target_engine,
                regime=ctx.regime_name,
                market_environment=ctx.market_env,
                cluster_cap=0.25,
                kappa_shrinkage_threshold=float(self.settings.features.kappa_shrinkage_threshold),
                default_shrinkage_intensity=float(self.settings.features.default_shrinkage_intensity),
                adaptive_fallback_profile=str(self.settings.features.adaptive_fallback_profile),
                benchmark_returns=ctx.bench_rets,
                market_neutral=(actual_profile == "market_neutral"),
            )

            returns_for_opt = ctx.train_rets if actual_profile == "market" else ctx.train_rets_strat

            # SOLVER CALL (Hardened by decorators in library)
            opt_resp = solver.optimize(returns=returns_for_opt, clusters=ctx.clusters, meta=ctx.window_meta, stats=self.stats, request=req)

            if ctx.is_meta:
                flat_weights = opt_resp.weights
            else:
                flat_weights = self.synthesizer.flatten_weights(opt_resp.weights)

            if flat_weights.empty:
                # Automatic fallback to Equal Weight if solver failed even with hardening
                flat_weights = self._get_equal_weight_flat(returns_for_opt, ctx.is_meta)

            self._apply_diversity_constraints(flat_weights)

            if self.ledger:
                weights_dict = flat_weights.set_index("Symbol")["Net_Weight"].to_dict()
                self.ledger.record_outcome(
                    step="backtest_optimize",
                    status="success",
                    output_hashes={},
                    metrics={"weights": weights_dict},
                    context=opt_ctx,
                )

            for sim_name in sim_names:
                self._run_simulation(sim_name, target_engine, ctx.profile, ctx.window, flat_weights, ctx.test_rets)

        except Exception as e:
            if self.ledger:
                self.ledger.record_outcome(step="backtest_optimize", status="error", output_hashes={}, metrics={"error": str(e)}, context=opt_ctx)

    def _run_simulation(
        self,
        sim_name: str,
        target_engine: str,
        profile: str,
        window: WalkForwardWindow,
        final_flat_weights: pd.DataFrame,
        test_rets: pd.DataFrame,
    ) -> None:
        """Runs simulation and records results."""
        sim_ctx = {
            "window_index": window.step_index,
            "engine": target_engine,
            "profile": profile,
            "simulator": sim_name,
        }
        try:
            simulator = build_simulator(sim_name)
            state_key = f"{target_engine}_{sim_name}_{profile}"
            last_state = self.current_holdings.get(state_key)

            sim_results = simulator.simulate(weights_df=final_flat_weights, returns=test_rets, initial_holdings=last_state)

            if isinstance(sim_results, dict):
                self.current_holdings[state_key] = sim_results.get("final_holdings")
            else:
                self.current_holdings[state_key] = getattr(sim_results, "final_holdings", None)

            metrics = sim_results.get("metrics", sim_results) if isinstance(sim_results, dict) else getattr(sim_results, "metrics", {})

            # Record returns
            daily_rets = metrics.get("daily_returns")
            if isinstance(daily_rets, pd.Series):
                self.return_series.setdefault(state_key, []).append(daily_rets.clip(-1.0, 1.0))

            if self.ledger:
                self.ledger.record_outcome(step="backtest_simulate", status="success", output_hashes={}, metrics=metrics, context=sim_ctx)

            self.results.append({"window": window.step_index, "engine": target_engine, "profile": profile, "simulator": sim_name, "metrics": metrics})
        except Exception as e:
            if self.ledger:
                self.ledger.record_outcome(step="backtest_simulate", status="error", output_hashes={}, metrics={"error": str(e)}, context=sim_ctx)

    def _apply_diversity_constraints(self, flat_weights: pd.DataFrame):
        """Standardizes weight clipping and normalization."""
        w_sum_abs = flat_weights["Weight"].sum()
        if w_sum_abs > 0:
            flat_weights["Weight"] = flat_weights["Weight"].clip(upper=0.25 * w_sum_abs)
            flat_weights["Net_Weight"] = flat_weights["Net_Weight"].clip(lower=-0.25 * w_sum_abs, upper=0.25 * w_sum_abs)
            new_sum = flat_weights["Weight"].sum()
            if new_sum > 0:
                scale = w_sum_abs / new_sum
                flat_weights["Weight"] *= scale
                flat_weights["Net_Weight"] *= scale

    def _get_equal_weight_flat(self, returns_for_opt: pd.DataFrame, is_meta: bool) -> pd.DataFrame:
        """Returns equal-weighted portfolio weights."""
        n_strat = len(returns_for_opt.columns)
        if n_strat > 0:
            ew_weights = pd.Series(1.0 / n_strat, index=returns_for_opt.columns)
            dummy_weights = pd.DataFrame({"Symbol": ew_weights.index, "Weight": ew_weights.values})
            return dummy_weights if is_meta else self.synthesizer.flatten_weights(dummy_weights)
        return pd.DataFrame()

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

    def _record_selection_audit(self, selection, winners_syms, train_rets, engine_name, window_index):
        if self.ledger:
            metrics_payload = {
                "n_universe_symbols": len(self.returns.columns),
                "n_refinement_candidates": len(train_rets.columns),
                "n_winners": len(winners_syms),
                "winners": winners_syms,
                **selection.metrics,
            }
            self.ledger.record_outcome(
                step="backtest_select",
                status="success",
                output_hashes={},
                metrics=metrics_payload,
                data={
                    "relaxation_stage": selection.relaxation_stage,
                    "winners_meta": selection.winners,
                },
                context={"window_index": window_index, "engine": engine_name},
            )

    def _save_artifacts(self, run_dir: Path):
        """
        Persists stitched return series and profile aliases to disk.
        (Standard: Parquet format for institutional auditability).
        """
        returns_out = run_dir / "data" / "returns"
        returns_out.mkdir(parents=True, exist_ok=True)
        for key, series_list in self.return_series.items():
            if series_list:
                full_series = cast(pd.Series, pd.concat(series_list))
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
