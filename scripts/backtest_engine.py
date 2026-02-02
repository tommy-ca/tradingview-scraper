from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

sys.path.append(os.getcwd())
from dataclasses import dataclass

from tradingview_scraper.backtest.orchestration import WalkForwardOrchestrator, WalkForwardWindow
from tradingview_scraper.orchestration.strategies import StrategyFactory
from tradingview_scraper.portfolio_engines import EngineRequest, ProfileName, build_engine, build_simulator
from tradingview_scraper.portfolio_engines.utils import harden_solve
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.selection_engines import build_selection_engine, get_hierarchical_clusters
from tradingview_scraper.selection_engines.base import SelectionRequest
from tradingview_scraper.settings import TradingViewScraperSettings, get_settings
from tradingview_scraper.utils.audit import AuditLedger
from tradingview_scraper.utils.data_utils import ensure_utc_index
from tradingview_scraper.utils.synthesis import StrategySynthesizer


@dataclass(frozen=True)
class SimulationContext:
    engine_name: str
    profile: str
    window: WalkForwardWindow
    regime_name: str
    market_env: str
    train_rets: pd.DataFrame
    train_rets_strat: pd.DataFrame
    clusters: dict[str, list[str]]
    window_meta: dict[str, Any]
    bench_rets: pd.Series | None
    is_meta: bool
    test_rets: pd.DataFrame


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backtest_engine")


def _get_annualization_factor(series: pd.Series) -> float:
    """Determine annualization factor based on frequency."""
    if series.empty:
        return 252.0
    if len(series) < 2:
        return 252.0

    idx = series.index
    if not isinstance(idx, (pd.DatetimeIndex, pd.Index)):
        return 252.0

    try:
        diff = cast(Any, idx[1]) - cast(Any, idx[0])
        if diff <= pd.Timedelta(hours=1):
            return 252.0 * 24.0
        elif diff <= pd.Timedelta(days=1):
            return 252.0
    except (IndexError, TypeError):
        pass
    return 252.0


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
        import json

        json.dump(results["meta"], f, indent=2)


class BacktestEngine:
    def __init__(self, settings: TradingViewScraperSettings | None = None):
        self.settings = settings or get_settings()
        self.returns = pd.DataFrame()
        self.features_matrix = pd.DataFrame()  # Dynamic Feature Matrix
        self.metadata = {}
        self.stats = pd.DataFrame()

        # State Accumulators (Refactor: Issue 017 reduction)
        self.results: list[dict[str, Any]] = []
        self.return_series: dict[str, list[pd.Series]] = {}
        self.current_holdings: dict[str, Any] = {}
        self.ledger: AuditLedger | None = None
        self.synthesizer = StrategySynthesizer()

        # CR-265: Initialize Regime Detector
        self.detector = MarketRegimeDetector(enable_audit_log=False)

    def load_data(self, run_dir: Path | None = None):
        """
        Loads returns and metadata from lakehouse or specific run directory.

        Args:
            run_dir: Optional path to a specific run directory. If None, finds latest.

        Audit:
            - Security: Validates pickle paths against allowed directories.
            - Integrity: Enforces UTC DatetimeIndex on loaded data.
        """
        if not run_dir:
            # Try to find latest run if not provided
            runs_dir = self.settings.summaries_runs_dir
            if runs_dir.exists():
                latest_runs = sorted(
                    [d for d in runs_dir.iterdir() if d.is_dir() and (d / "data" / "returns_matrix.parquet").exists()],
                    key=os.path.getmtime,
                    reverse=True,
                )
                if latest_runs:
                    run_dir = cast(Path, latest_runs[0])

        data_dir = (run_dir / "data") if run_dir else self.settings.lakehouse_dir
        logger.info(f"Loading data from {data_dir}")

        # 1. Load Candidates (Deterministic Path)
        cands_priority = [data_dir / "portfolio_candidates_raw.json", data_dir / "portfolio_candidates.json"]
        self.raw_candidates = []
        for p in cands_priority:
            if p.exists():
                with open(p, "r") as f:
                    self.raw_candidates = json.load(f)
                break

        # 2. Load Returns Matrix (Deterministic Priority + Security Guard)
        returns_priority = [
            data_dir / "returns_matrix.parquet",
            data_dir / "portfolio_returns.pkl",
            self.settings.lakehouse_dir / "returns_matrix.parquet",
        ]
        returns_path = next((p for p in returns_priority if p.exists()), None)
        if not returns_path:
            raise FileNotFoundError(f"Returns matrix not found in {data_dir} or lakehouse")

        # Security: Verify returns_path is under allowed directories if it's a pickle
        if returns_path.suffix == ".pkl":
            allowed = [self.settings.summaries_runs_dir.resolve(), self.settings.lakehouse_dir.resolve()]
            resolved_p = returns_path.resolve()
            if not any(resolved_p.is_relative_to(a) for a in allowed):
                raise ValueError(f"Secure Pickle Loading violation: {returns_path} is outside allowed directories.")

        if returns_path.suffix == ".parquet":
            self.returns = pd.read_parquet(returns_path)
        else:
            self.returns = pd.read_pickle(returns_path)

        # Ensure UTC DatetimeIndex
        self.returns = cast(pd.DataFrame, ensure_utc_index(self.returns))

        # 3. Load Features Matrix
        features_priority = [data_dir / "features_matrix.parquet", self.settings.lakehouse_dir / "features_matrix.parquet"]
        features_path = next((p for p in features_priority if p.exists()), None)
        if features_path:
            try:
                self.features_matrix = pd.read_parquet(features_path)
                self.features_matrix = cast(pd.DataFrame, ensure_utc_index(self.features_matrix))
                logger.info(f"Loaded Features Matrix: {self.features_matrix.shape}")
            except Exception as e:
                logger.warning(f"Failed to load features matrix: {e}")

        # 4. Load Metadata
        metadata_priority = [data_dir / "metadata_catalog.json", data_dir / "portfolio_meta.json"]
        metadata_path = next((p for p in metadata_priority if p.exists()), None)
        if metadata_path:
            with open(metadata_path, "r") as f:
                self.metadata = json.load(f)

        # 5. Load Stats Matrix
        stats_priority = [data_dir / "stats_matrix.parquet", data_dir / "antifragility_stats.json"]
        stats_path = next((p for p in stats_priority if p.exists()), None)
        if stats_path:
            if stats_path.suffix == ".parquet":
                self.stats = pd.read_parquet(stats_path)
            else:
                try:
                    self.stats = pd.read_json(stats_path)
                except Exception:
                    logger.warning(f"Failed to parse JSON stats at {stats_path}")
                    self.stats = pd.DataFrame()

    def _is_meta_profile(self, profile_name: str) -> bool:
        """
        Checks if the specified profile defines recursive sleeves in the manifest.

        Args:
            profile_name: Name of the profile to check.

        Returns:
            bool: True if it's a meta-profile.
        """
        manifest_path = self.settings.manifest_path
        if not manifest_path.exists():
            return False
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        prof_cfg = manifest.get("profiles", {}).get(profile_name, {})
        return "sleeves" in prof_cfg

    def _prepare_meta_returns(self, config: TradingViewScraperSettings, run_dir: Path | None) -> bool:
        """
        Establishes meta-returns matrix for fractal backtesting recursive simulation.

        Args:
            config: Active platform settings.
            run_dir: Directory for storing intermediate meta-artifacts.

        Returns:
            bool: True if establishment succeeded.
        """
        logger.info(f"🚀 RECURSIVE META-BACKTEST DETECTED: {config.profile}")

        if not run_dir:
            run_dir = self.settings.prepare_summaries_run_dir()

        anchor_prof = "hrp"
        temp_meta_path = run_dir / "data" / f"meta_returns_{config.profile}_{anchor_prof}.pkl"

        # Deferred import to avoid circular dependency
        from scripts.build_meta_returns import build_meta_returns

        build_meta_returns(
            meta_profile=config.profile,
            output_path=str(run_dir / "data" / "meta.pkl"),
            profiles=[anchor_prof],
            manifest_path=config.manifest_path,
            base_dir=run_dir / "data",
        )

        if temp_meta_path.exists():
            data = pd.read_pickle(temp_meta_path)
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

    def _apply_dynamic_filter(self, current_date: pd.Timestamp, train_rets: pd.DataFrame) -> pd.DataFrame:
        """
        Filters candidates based on historical ratings at the current point-in-time.

        Args:
            current_date: Current timestamp for point-in-time lookup.
            train_rets: Candidate return matrix.

        Returns:
            pd.DataFrame: Filtered return matrix.

        Audit:
            - Numerical: Ensures at least 2 assets remain after filtering.
        """
        if self.features_matrix.empty:
            return train_rets

        idx_loc = self.features_matrix.index.searchsorted(current_date)
        if idx_loc <= 0:
            return train_rets

        try:
            if current_date in self.features_matrix.index:
                current_features = self.features_matrix.loc[current_date]
            else:
                prev_date = self.features_matrix.index[self.features_matrix.index < current_date][-1]
                current_features = self.features_matrix.loc[prev_date]

            if isinstance(self.features_matrix.columns, pd.MultiIndex):
                ratings = current_features.xs("recommend_all", level="feature")
            else:
                ratings = current_features

            min_rating = 0.0
            valid_symbols = ratings[ratings > min_rating].index.tolist()
            valid_universe = [s for s in valid_symbols if s in train_rets.columns]

            if len(valid_universe) >= 2:
                logger.info(f"  Dynamic Filter: {len(valid_universe)} / {len(ratings)} valid candidates (Rating > {min_rating})")
                return cast(pd.DataFrame, train_rets[valid_universe])
            else:
                logger.warning(f"  Dynamic Filter too strict (found {len(valid_universe)}). Falling back to full universe.")
        except Exception as e:
            logger.warning(f"  Dynamic Filter failed: {e}. Using static universe.")

        return train_rets

    def _detect_market_regime(self, train_rets: pd.DataFrame) -> tuple[str, str]:
        """
        Detects current market regime and environment quadrant.

        Args:
            train_rets: Training return matrix.

        Returns:
            tuple[str, str]: (regime_name, environment_quadrant)
        """
        regime_name = "NORMAL"
        market_env = "NORMAL"
        try:
            if not train_rets.empty and len(train_rets) > 60:
                regime_label, _, quadrant = self.detector.detect_regime(train_rets)
                regime_name = regime_label
                market_env = quadrant
        except Exception as e:
            logger.warning(f"  Regime detection failed: {e}")
        return regime_name, market_env

    def run_tournament(
        self,
        mode: str = "production",
        train_window: int | None = None,
        test_window: int | None = None,
        step_size: int | None = None,
        run_dir: Path | None = None,
        lightweight: bool = False,
    ):
        """
        Runs a rolling-window backtest tournament across multiple engines/profiles.

        Args:
            mode: Run mode ('production' or 'research').
            train_window: Size of training period.
            test_window: Size of test period.
            step_size: Number of bars to advance per window.
            run_dir: Directory for storing outputs.
            lightweight: If True, only runs HRP for fast verification.

        Returns:
            dict[str, Any]: Tournament results and stitched return streams.

        Audit:
            - Compliance: Adheres to 3-Pillar Architecture.
            - Traceability: Records all intents and outcomes in AuditLedger.
        """
        if self.returns.empty:
            self.load_data(run_dir=run_dir)

        self.config = self.settings
        is_meta = self._is_meta_profile(self.config.profile or "")

        resolved_train = int(train_window or self.config.train_window)
        resolved_test = int(test_window or self.config.test_window)
        resolved_step = int(step_size or self.config.step_size)

        if is_meta:
            if not self._prepare_meta_returns(self.config, run_dir):
                return {"results": [], "meta": {}}

        # Tournament configuration
        if lightweight:
            self.profiles = ["hrp"]
            self.engines = ["custom"]
            self.sim_names = ["vectorbt"]
        else:
            self.profiles = self.config.profiles.split(",")
            self.engines = self.config.engines.split(",")
            self.sim_names = self.config.backtest_simulators.split(",")

        self.results = []
        self.return_series = {}
        self.current_holdings = {}
        self.lightweight = lightweight

        results_meta = {
            "mode": mode,
            "train_window": resolved_train,
            "test_window": resolved_test,
            "step_size": resolved_step,
            "profiles": self.profiles,
            "engines": self.engines,
            "simulators": self.sim_names,
            "lightweight": lightweight,
        }

        if not run_dir:
            run_dir = self.settings.prepare_summaries_run_dir()

        self.ledger = AuditLedger(run_dir)

        orchestrator = WalkForwardOrchestrator(
            train_window=resolved_train,
            test_window=resolved_test,
            step_size=resolved_step,
            anchored=False,
        )

        windows = list(orchestrator.generate_windows(self.returns))
        logger.info(f"Tournament Started: {len(self.returns)} rows available. Windows: count={len(windows)}, train={resolved_train}, test={resolved_test}, step={resolved_step}")

        for window in windows:
            self._run_window_step(window, orchestrator, is_meta)

        # Save artifacts
        self._save_tournament_artifacts(run_dir)

        final_series_map = {key: pd.concat(series_list).sort_index() for key, series_list in self.return_series.items() if series_list}
        return {"results": self.results, "meta": results_meta, "stitched_returns": final_series_map}

    def _run_window_step(self, window: WalkForwardWindow, orchestrator: WalkForwardOrchestrator, is_meta: bool):
        """
        Executes selection, synthesis, and optimization for a single time window.

        Args:
            window: Current window definition.
            orchestrator: Active time-stepping orchestrator.
            is_meta: Whether this is a meta-portfolio run.

        Audit:
            - Performance: Uses vectorized synthesis and hierarchical clustering.
        """
        current_date = cast(pd.Timestamp, window.test_dates[0])
        train_rets_raw, test_rets_raw = orchestrator.slice_data(cast(pd.DataFrame, self.returns), window)
        train_rets = cast(pd.DataFrame, train_rets_raw)
        test_rets = cast(pd.DataFrame, test_rets_raw)

        # 1. Dynamic Filtering
        if not is_meta:
            train_rets = self._apply_dynamic_filter(current_date, train_rets)

        # 2. Regime Detection
        regime_name, market_env = self._detect_market_regime(train_rets)

        # 3. Pillar 1: Universe Selection
        strategy = StrategyFactory.infer_strategy(self.config.profile or "", self.config.strategy)
        selection_engine = build_selection_engine(self.config.features.selection_mode)

        req_select = SelectionRequest(
            top_n=self.config.top_n,
            threshold=self.config.threshold,
            strategy=strategy,
        )
        selection = selection_engine.select(returns=train_rets, raw_candidates=self.raw_candidates, stats_df=self.stats, request=req_select)

        # Filter winners missing from returns matrix
        if selection.winners:
            selection_winners = [w for w in selection.winners if w["symbol"] in train_rets.columns]
            object.__setattr__(selection, "winners", selection_winners)

        if not selection.winners:
            return

        winners_syms = [w["symbol"] for w in selection.winners]
        window_meta = self.metadata.copy()
        for w in selection.winners:
            window_meta[w["symbol"]] = w

        if self.ledger and not self.lightweight:
            self._record_selection_audit(selection, winners_syms, train_rets, selection_engine.name, window.step_index)

        # 4. Pillar 2: Strategy Synthesis
        if is_meta:
            train_rets_strat_raw = train_rets[winners_syms]
        else:
            train_rets_strat_raw = self.synthesizer.synthesize(train_rets, selection.winners, self.config.features)

        train_rets_strat = cast(pd.DataFrame, train_rets_strat_raw)

        # 5. Pillar 3: Allocation & Simulation
        new_cluster_ids, _ = get_hierarchical_clusters(train_rets_strat, float(self.config.threshold), 25)
        stringified_clusters = {}
        for sym, c_id in zip(train_rets_strat.columns, new_cluster_ids):
            stringified_clusters.setdefault(str(c_id), []).append(str(sym))

        bench_sym = self.config.benchmark_symbols[0] if self.config.benchmark_symbols else None
        bench_rets = train_rets[bench_sym] if bench_sym and bench_sym in train_rets.columns else None

        for engine_name in self.engines:
            profiles_to_run = ["adaptive"] if engine_name == "adaptive" else self.profiles
            for profile in profiles_to_run:
                sim_ctx = SimulationContext(
                    engine_name=engine_name,
                    profile=profile,
                    window=window,
                    regime_name=regime_name,
                    market_env=market_env,
                    train_rets=train_rets,
                    train_rets_strat=train_rets_strat,
                    clusters=stringified_clusters,
                    window_meta=window_meta,
                    bench_rets=cast(pd.Series, bench_rets) if bench_rets is not None else None,
                    is_meta=is_meta,
                    test_rets=test_rets,
                )
                self._process_optimization_window(sim_ctx)

    def _record_selection_audit(self, selection, winners_syms: list[str], train_rets: pd.DataFrame, engine_name: str, window_index: int):
        """
        Records the outcome of the Pillar 1 Universe Selection stage.

        Args:
            selection: Selection result object.
            winners_syms: List of winning symbol IDs.
            train_rets: Training return matrix.
            engine_name: Name of the selection engine.
            window_index: Current walk-forward step index.
        """
        metrics_payload = {
            "n_universe_symbols": len(self.returns.columns),
            "n_refinement_candidates": len(train_rets.columns),
            "n_discovery_candidates": 0,
            "n_winners": len(winners_syms),
            "winners": winners_syms,
            **selection.metrics,
        }
        pipeline_audit = metrics_payload.pop("pipeline_audit", None)
        data_payload = {
            "relaxation_stage": selection.relaxation_stage,
            "audit_clusters": selection.audit_clusters,
            "winners_meta": selection.winners,
        }
        if pipeline_audit:
            data_payload["pipeline_audit"] = pipeline_audit

        if self.ledger:
            self.ledger.record_outcome(
                step="backtest_select",
                status="success",
                output_hashes={},
                metrics=metrics_payload,
                data=data_payload,
                context={"window_index": window_index, "engine": engine_name},
            )

    def _process_optimization_window(self, ctx: SimulationContext):
        """
        Processes a single optimization window with hardening and simulation.

        Args:
            ctx: Simulation context containing all necessary data and state.

        Audit:
            - Stability: Delegates to harden_solve utility for Ridge retries.
            - Integrity: Applies diversity constraints and simulation verification.
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
            if self.ledger and not self.lightweight:
                self.ledger.record_intent("backtest_optimize", opt_ctx, input_hashes={})

            req = EngineRequest(
                profile=actual_profile,
                engine=target_engine,
                regime=ctx.regime_name,
                market_environment=ctx.market_env,
                cluster_cap=0.25,
                kappa_shrinkage_threshold=float(self.config.features.kappa_shrinkage_threshold),
                default_shrinkage_intensity=float(self.config.features.default_shrinkage_intensity),
                adaptive_fallback_profile=str(self.config.features.adaptive_fallback_profile),
                benchmark_returns=ctx.bench_rets,
                market_neutral=(actual_profile == "market_neutral"),
            )

            returns_for_opt = ctx.train_rets if actual_profile == "market" else ctx.train_rets_strat

            # Use hardening utility
            final_flat_weights = harden_solve(
                solver=solver,
                returns=returns_for_opt,
                clusters=ctx.clusters,
                window_meta=ctx.window_meta,
                stats=self.stats,
                request=req,
                test_rets=ctx.test_rets,
                sim_name=self.sim_names[0],
                current_holdings=self.current_holdings,
                synthesizer=self.synthesizer,
                is_meta=ctx.is_meta,
                apply_constraints_fn=self._apply_diversity_constraints,
                get_ew_fn=lambda: self._get_equal_weight_flat(returns_for_opt, ctx.is_meta),
                ledger=self.ledger,
            )

            if final_flat_weights.empty:
                return

            if self.ledger and not self.lightweight:
                weights_dict = final_flat_weights.set_index("Symbol")["Net_Weight"].to_dict()
                self.ledger.record_outcome(
                    step="backtest_optimize",
                    status="success",
                    output_hashes={},
                    metrics={"weights": weights_dict},
                    context=opt_ctx,
                )

            for sim_name in self.sim_names:
                self._run_simulation(
                    sim_name=sim_name,
                    target_engine=target_engine,
                    profile=ctx.profile,
                    window=ctx.window,
                    final_flat_weights=final_flat_weights,
                    test_rets=ctx.test_rets,
                )

        except Exception as e:
            if self.ledger and not self.lightweight:
                self.ledger.record_outcome(step="backtest_optimize", status="error", output_hashes={}, metrics={"error": str(e)}, context=opt_ctx)

    def _run_simulation(
        self,
        sim_name: str,
        target_engine: str,
        profile: str,
        window: Any,
        final_flat_weights: pd.DataFrame,
        test_rets: pd.DataFrame,
    ):
        """
        Runs a simulation for the provided weights and captures metrics.

        Args:
            sim_name: Name of the simulator engine.
            target_engine: Name of the optimization engine.
            profile: Optimization profile.
            window: Current window.
            final_flat_weights: Optimized asset weights.
            test_rets: Out-of-sample returns.
        """
        sim_ctx = {
            "window_index": window.step_index,
            "engine": target_engine,
            "profile": profile,
            "simulator": sim_name,
            "selection_mode": self.config.features.selection_mode,
        }
        try:
            simulator = build_simulator(sim_name)
            if self.ledger and not self.lightweight:
                self.ledger.record_intent("backtest_simulate", sim_ctx, input_hashes={})

            state_key = f"{target_engine}_{sim_name}_{profile}"
            last_state = self.current_holdings.get(state_key)
            sim_results = simulator.simulate(weights_df=final_flat_weights, returns=test_rets, initial_holdings=last_state)

            if isinstance(sim_results, dict):
                self.current_holdings[state_key] = sim_results.get("final_holdings") or sim_results.get("final_weights")
            else:
                self.current_holdings[state_key] = getattr(sim_results, "final_holdings", getattr(sim_results, "final_weights", None))

            metrics = sim_results.get("metrics", sim_results) if isinstance(sim_results, dict) else getattr(sim_results, "metrics", {})
            sanitized_metrics = {}

            if "top_assets" in metrics:
                top_assets = metrics["top_assets"]
                if isinstance(top_assets, list):
                    sanitized_metrics["concentration_hhi"] = float(sum([a.get("Weight", 0) ** 2 for a in top_assets]))
                    sanitized_metrics["top_assets"] = top_assets

            for k, v in metrics.items():
                if isinstance(v, (int, float, np.number, str, bool, type(None))):
                    sanitized_metrics[k] = float(v) if isinstance(v, (np.number, float, int)) else v

            daily_rets = metrics.get("daily_returns")
            if isinstance(daily_rets, pd.Series):
                key = f"{target_engine}_{sim_name}_{profile}"
                self.return_series.setdefault(key, []).append(daily_rets.clip(-1.0, 1.0))

            if self.ledger and not self.lightweight:
                data_payload = {"daily_returns": daily_rets.values.tolist() if isinstance(daily_rets, pd.Series) else (daily_rets if isinstance(daily_rets, list) else [])}
                if isinstance(daily_rets, pd.Series):
                    data_payload["ann_factor"] = _get_annualization_factor(daily_rets)
                self.ledger.record_outcome(step="backtest_simulate", status="success", output_hashes={}, metrics=sanitized_metrics, data=data_payload, context=sim_ctx)

            self.results.append({"window": window.step_index, "engine": target_engine, "profile": profile, "simulator": sim_name, "metrics": sanitized_metrics})
        except Exception as e:
            if self.ledger and not self.lightweight:
                self.ledger.record_outcome(step="backtest_simulate", status="error", output_hashes={}, metrics={"error": str(e)}, context=sim_ctx)

    def _save_tournament_artifacts(self, run_dir: Path):
        """
        Persists stitched return series and profile aliases to disk.

        Args:
            run_dir: Directory where artifacts should be saved.
        """
        returns_out = run_dir / "data" / "returns"
        returns_out.mkdir(parents=True, exist_ok=True)
        for key, series_list in self.return_series.items():
            if not series_list:
                continue
            try:
                full_series_raw = pd.concat(series_list)
                # Cast to pd.Series and ensure DatetimeIndex for sorting
                full_series = cast(pd.Series, full_series_raw[~full_series_raw.index.duplicated(keep="first")])
                full_series = full_series.sort_index()
                out_path = returns_out / f"{key}.pkl"
                full_series.to_pickle(str(out_path))

                parts = key.split("_")
                if len(parts) >= 3:
                    prof_name = "_".join(parts[2:])
                    alias_path = returns_out / f"{prof_name}.pkl"
                    if not alias_path.exists():
                        full_series.to_pickle(str(alias_path))
            except Exception as e:
                logger.error(f"Failed to save returns for {key}: {e}")

    def _apply_diversity_constraints(self, flat_weights: pd.DataFrame):
        """
        Standardizes weight clipping and normalization to ensure portfolio diversity.

        Args:
            flat_weights: Asset weights to be constrained.
        """
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
        """
        Returns an equal-weighted portfolio for failed or unstable windows.

        Args:
            returns_for_opt: Return streams available for allocation.
            is_meta: Whether this is a meta-portfolio run.

        Returns:
            pd.DataFrame: Equal-weighted portfolio weights.
        """
        n_strat = len(returns_for_opt.columns)
        if n_strat > 0:
            ew_weights = pd.Series(1.0 / n_strat, index=returns_for_opt.columns)
            dummy_weights = pd.DataFrame({"Symbol": ew_weights.index, "Weight": ew_weights.values})
            return dummy_weights if is_meta else self.synthesizer.flatten_weights(dummy_weights)
        return pd.DataFrame()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tournament Backtest Engine")
    parser.add_argument("--mode", choices=["production", "research"], default="research")
    parser.add_argument("--train-window", type=int)
    parser.add_argument("--test-window", type=int)
    parser.add_argument("--step-size", type=int)
    parser.add_argument("--run-id", help="Explicit run ID to use")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    config = get_settings()

    # If run_id is provided, ensure settings uses it
    if args.run_id:
        os.environ["TV_RUN_ID"] = args.run_id
        # Reload settings to pick up env var
        config = get_settings()

    run_dir = config.prepare_summaries_run_dir()

    engine = BacktestEngine()
    tournament_results = engine.run_tournament(mode=args.mode, train_window=args.train_window, test_window=args.test_window, step_size=args.step_size, run_dir=run_dir)

    persist_tournament_artifacts(tournament_results, run_dir / "data")

    print("\n" + "=" * 50)
    print("TOURNAMENT COMPLETE")
    print("=" * 50)
