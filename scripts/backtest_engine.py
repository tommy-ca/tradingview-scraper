import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

sys.path.append(os.getcwd())
from tradingview_scraper.portfolio_engines import EngineRequest, ProfileName, build_engine, build_simulator
from tradingview_scraper.selection_engines import build_selection_engine, get_hierarchical_clusters
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger
from tradingview_scraper.utils.synthesis import StrategySynthesizer

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backtest_engine")


def _get_annualization_factor(series: pd.Series) -> float:
    """Determine annualization factor based on frequency."""
    if series.empty:
        return 252.0
    if len(series) < 2:
        return 252.0

    idx = series.index
    if not hasattr(idx, "__getitem__"):
        return 252.0

    diff = cast(Any, idx[1]) - cast(Any, idx[0])
    if diff <= pd.Timedelta(hours=1):
        return 252.0 * 24.0
    elif diff <= pd.Timedelta(days=1):
        return 252.0
    return 252.0


def persist_tournament_artifacts(results: dict[str, Any], output_dir: Path):
    """Save tournament results to structured files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results["results"]).to_csv(output_dir / "tournament_results.csv", index=False)
    with open(output_dir / "tournament_meta.json", "w") as f:
        import json

        json.dump(results["meta"], f, indent=2)


class BacktestEngine:
    def __init__(self):
        self.settings = get_settings()
        self.returns = pd.DataFrame()
        self.features_matrix = pd.DataFrame()  # Dynamic Feature Matrix
        self.metadata = {}
        self.stats = pd.DataFrame()

        # CR-265: Initialize Regime Detector
        from tradingview_scraper.regime import MarketRegimeDetector

        self.detector = MarketRegimeDetector(enable_audit_log=False)

    def load_data(self, run_dir: Path | None = None):
        """Load returns and metadata from lakehouse or run directory."""
        if not run_dir:
            # Try to find latest run if not provided
            runs_dir = self.settings.summaries_runs_dir
            if runs_dir.exists():
                latest_runs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and (d / "data" / "returns_matrix.parquet").exists()], key=os.path.getmtime, reverse=True)
                if latest_runs:
                    run_dir = cast(Path, latest_runs[0])

        data_dir = run_dir / "data" if run_dir else self.settings.lakehouse_dir
        logger.info(f"Loading data from {data_dir}")

        # Load Candidates
        cands_path = data_dir / "portfolio_candidates_raw.json"
        if not cands_path.exists():
            cands_path = data_dir / "portfolio_candidates.json"

        self.raw_candidates = []
        if cands_path.exists():
            with open(cands_path, "r") as f:
                self.raw_candidates = json.load(f)

        # Search for returns matrix in data_dir, then fallback to lakehouse
        search_dirs = [data_dir, self.settings.lakehouse_dir]
        search_files = ["returns_matrix.parquet", "portfolio_returns.pkl", "returns_matrix.pkl"]

        returns_path = None
        for d in search_dirs:
            for f in search_files:
                p = d / f
                if p.exists():
                    returns_path = p
                    break
            if returns_path:
                break

        if not returns_path:
            raise FileNotFoundError(f"Returns matrix not found in {data_dir} or {self.settings.lakehouse_dir}")

        if str(returns_path).endswith(".parquet"):
            self.returns = pd.read_parquet(returns_path)
        else:
            self.returns = pd.read_pickle(returns_path)

        # CR-FIX: Ensure DatetimeIndex (Phase 225)
        if not isinstance(self.returns.index, pd.DatetimeIndex):
            self.returns.index = pd.to_datetime(self.returns.index)
        if self.returns.index.tz is not None:
            self.returns.index = self.returns.index.tz_convert(None)

        # Load Features Matrix (Dynamic Backtesting)
        features_path = data_dir / "features_matrix.parquet"
        if not features_path.exists():
            features_path = self.settings.lakehouse_dir / "features_matrix.parquet"

        if features_path.exists():
            try:
                self.features_matrix = pd.read_parquet(features_path)
                logger.info(f"Loaded Features Matrix: {self.features_matrix.shape}")
                # Ensure index alignment
                if not isinstance(self.features_matrix.index, pd.DatetimeIndex):
                    self.features_matrix.index = pd.to_datetime(self.features_matrix.index)
                if self.features_matrix.index.tz is not None:
                    self.features_matrix.index = self.features_matrix.index.tz_convert(None)
            except Exception as e:
                logger.warning(f"Failed to load features matrix: {e}")

        metadata_path = data_dir / "metadata_catalog.json"
        if not metadata_path.exists():
            metadata_path = data_dir / "portfolio_meta.json"

        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                self.metadata = json.load(f)

        stats_path = data_dir / "stats_matrix.parquet"
        if not stats_path.exists():
            stats_path = data_dir / "antifragility_stats.json"

        if stats_path.exists():
            if str(stats_path).endswith(".parquet"):
                self.stats = pd.read_parquet(stats_path)
            else:
                try:
                    self.stats = pd.read_json(stats_path)
                except Exception:
                    self.stats = pd.DataFrame()

    def _is_meta_profile(self, profile_name: str) -> bool:
        """Checks if a profile is a meta-portfolio (contains sleeves)."""
        manifest_path = self.settings.manifest_path
        if not manifest_path.exists():
            return False
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        prof_cfg = manifest.get("profiles", {}).get(profile_name, {})
        return "sleeves" in prof_cfg

    def _get_sleeve_returns(self, sleeve: Dict, train_window: int, test_window: int, step_size: int) -> pd.Series:
        """
        Generates walk-forward returns for a sub-sleeve.
        Uses child engine and caching to minimize compute.
        """
        s_profile = sleeve["profile"]
        s_id = sleeve["id"]

        # CR-842: Recursive Caching (Phase 570)
        cache_dir = self.settings.lakehouse_dir / ".cache" / "backtests"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache key based on profile and window parameters
        cache_key = f"{s_profile}_{train_window}_{test_window}_{step_size}"
        cache_file = cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            logger.info(f"  [{s_id}] CACHE HIT: {cache_key}")
            return cast(pd.Series, pd.read_pickle(cache_file))

        logger.info(f"  [{s_id}] Simulating walk-forward returns for profile: {s_profile}")

        # 1. Create Child Engine
        child_engine = BacktestEngine()

        # 2. Configure Child Engine with sleeve profile settings
        original_profile = os.getenv("TV_PROFILE")
        os.environ["TV_PROFILE"] = s_profile

        try:
            # We must clear the settings cache to pick up the sub-profile
            get_settings.cache_clear()
            child_engine.load_data()

            # 3. Run child tournament in lightweight mode
            res = child_engine.run_tournament(mode="research", train_window=train_window, test_window=test_window, step_size=step_size, lightweight=True)

            stitched = res.get("stitched_returns", {})

            # Find any valid series
            sleeve_series = pd.Series()
            for k, series in stitched.items():
                if k.endswith("_hrp") or k.endswith("_vectorbt_hrp"):
                    sleeve_series = series
                    break

            if sleeve_series.empty and stitched:
                sleeve_series = next(iter(stitched.values()))

            if not sleeve_series.empty:
                sleeve_series.to_pickle(cache_file)
                return cast(pd.Series, sleeve_series)

        finally:
            # Restore environment
            if original_profile:
                os.environ["TV_PROFILE"] = original_profile
            else:
                os.environ.pop("TV_PROFILE", None)
            get_settings.cache_clear()

        return pd.Series()

    def _prepare_meta_returns(self, config, run_dir: Optional[Path]) -> bool:
        """Establishes meta-returns for fractal backtesting."""
        logger.info(f"🚀 RECURSIVE META-BACKTEST DETECTED: {config.profile}")
        from scripts.build_meta_returns import build_meta_returns

        if not run_dir:
            run_dir = self.settings.prepare_summaries_run_dir()

        anchor_prof = "hrp"
        temp_meta_path = run_dir / "data" / f"meta_returns_{config.profile}_{anchor_prof}.pkl"
        build_meta_returns(meta_profile=config.profile, output_path=str(run_dir / "data" / "meta.pkl"), profiles=[anchor_prof], manifest_path=config.manifest_path, base_dir=run_dir / "data")

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

    def _apply_dynamic_filter(self, current_date, train_rets: pd.DataFrame) -> pd.DataFrame:
        """Filters candidates based on historical ratings at current_date."""
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
                return train_rets[valid_universe]
            else:
                logger.warning(f"  Dynamic Filter too strict (found {len(valid_universe)}). Falling back to full universe.")
        except Exception as e:
            logger.warning(f"  Dynamic Filter failed: {e}. Using static universe.")

        return train_rets

    def _detect_market_regime(self, train_rets: pd.DataFrame) -> tuple[str, str]:
        """Detects market regime and environment."""
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
        train_window: Optional[int] = None,
        test_window: Optional[int] = None,
        step_size: Optional[int] = None,
        run_dir: Optional[Path] = None,
        lightweight: bool = False,
    ):
        """Run a rolling-window backtest tournament."""
        if self.returns.empty:
            self.load_data(run_dir=run_dir)

        config = self.settings
        is_meta = self._is_meta_profile(config.profile or "")

        resolved_train = int(train_window or config.train_window)
        resolved_test = int(test_window or config.test_window)
        resolved_step = int(step_size or config.step_size)

        if is_meta:
            if not self._prepare_meta_returns(config, run_dir):
                return {"results": [], "meta": {}}

        # Tournament configuration
        if lightweight:
            profiles = ["hrp"]
            engines = ["custom"]
            sim_names = ["vectorbt"]
        else:
            profiles = config.profiles.split(",")
            engines = config.engines.split(",")
            sim_names = config.backtest_simulators.split(",")

        results: list[dict[str, Any]] = []
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

        synthesizer = StrategySynthesizer()
        if not run_dir:
            run_dir = self.settings.prepare_summaries_run_dir()

        ledger = AuditLedger(run_dir)
        return_series: Dict[str, List[pd.Series]] = {}
        current_holdings: Dict[str, Any] = {}

        n_obs = len(self.returns)
        windows = list(range(resolved_train, n_obs - resolved_test, resolved_step))
        logger.info(f"Tournament Started: {n_obs} rows available. Windows: count={len(windows)}, train={resolved_train}, test={resolved_test}, step={resolved_step}")

        for i in windows:
            current_date = self.returns.index[i]
            train_rets = self.returns.iloc[i - resolved_train : i]
            test_rets = self.returns.iloc[i : i + resolved_test]

            # 1. Dynamic Filtering
            if not is_meta:
                train_rets = self._apply_dynamic_filter(current_date, train_rets)

            # 2. Regime Detection
            regime_name, market_env = self._detect_market_regime(train_rets)

            # 3. Pillar 1: Universe Selection
            from tradingview_scraper.orchestration.strategies import StrategyFactory

            strategy = StrategyFactory.infer_strategy(config.profile or "", config.strategy)

            selection_engine = build_selection_engine(config.features.selection_mode)
            from tradingview_scraper.selection_engines.base import SelectionRequest

            req_select = SelectionRequest(
                top_n=config.top_n,
                threshold=config.threshold,
                strategy=strategy,
            )
            selection = selection_engine.select(returns=train_rets, raw_candidates=self.raw_candidates, stats_df=self.stats, request=req_select)

            # CR-FIX: Filter winners missing from returns matrix
            if selection.winners:
                selection_winners = [w for w in selection.winners if w["symbol"] in train_rets.columns]
                object.__setattr__(selection, "winners", selection_winners)

            if not selection.winners:
                continue

            winners_syms = [w["symbol"] for w in selection.winners]
            window_meta = self.metadata.copy()
            for w in selection.winners:
                window_meta[w["symbol"]] = w

            if ledger and not lightweight:
                self._record_selection_audit(ledger, selection, winners_syms, train_rets, selection_engine.name, i)

            # 4. Pillar 2: Strategy Synthesis
            if is_meta:
                train_rets_strat = train_rets[winners_syms]
            else:
                train_rets_strat = synthesizer.synthesize(train_rets, selection.winners, config.features)

            # 5. Pillar 3: Allocation & Simulation
            new_cluster_ids, _ = get_hierarchical_clusters(train_rets_strat, float(config.threshold), 25)
            stringified_clusters = {}
            for sym, c_id in zip(train_rets_strat.columns, new_cluster_ids):
                stringified_clusters.setdefault(str(c_id), []).append(str(sym))

            bench_sym = config.benchmark_symbols[0] if config.benchmark_symbols else None
            bench_rets = train_rets[bench_sym] if bench_sym and bench_sym in train_rets.columns else None

            for engine_name in engines:
                profiles_to_run = ["adaptive"] if engine_name == "adaptive" else profiles
                for profile in profiles_to_run:
                    self._process_optimization_window(
                        engine_name,
                        profile,
                        i,
                        regime_name,
                        market_env,
                        train_rets,
                        train_rets_strat,
                        stringified_clusters,
                        window_meta,
                        bench_rets,
                        config,
                        is_meta,
                        synthesizer,
                        ledger,
                        lightweight,
                        sim_names,
                        test_rets,
                        current_holdings,
                        return_series,
                        results,
                    )

        # Save artifacts
        self._save_tournament_artifacts(run_dir, return_series)

        final_series_map = {key: pd.concat(series_list).sort_index() for key, series_list in return_series.items() if series_list}
        return {"results": results, "meta": results_meta, "stitched_returns": final_series_map}

    def _record_selection_audit(self, ledger, selection, winners_syms: list[str], train_rets: pd.DataFrame, engine_name: str, window_index: int):
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

        ledger.record_outcome(
            step="backtest_select",
            status="success",
            output_hashes={},
            metrics=metrics_payload,
            data=data_payload,
            context={"window_index": window_index, "engine": engine_name},
        )

    def _process_optimization_window(
        self,
        engine_name: str,
        profile: str,
        window_index: int,
        regime_name: str,
        market_env: str,
        train_rets: pd.DataFrame,
        train_rets_strat: pd.DataFrame,
        stringified_clusters: dict[str, list[str]],
        window_meta: dict[str, Any],
        bench_rets: pd.Series | None,
        config: Any,
        is_meta: bool,
        synthesizer: StrategySynthesizer,
        ledger: AuditLedger,
        lightweight: bool,
        sim_names: list[str],
        test_rets: pd.DataFrame,
        current_holdings: dict[str, Any],
        return_series: dict[str, list[pd.Series]],
        results: list[dict[str, Any]],
    ):
        actual_profile = cast(ProfileName, profile)
        target_engine = engine_name
        if actual_profile in ["market", "benchmark"]:
            target_engine = "market"
        elif actual_profile == "barbell":
            target_engine = "custom"

        opt_ctx = {
            "window_index": window_index,
            "engine": target_engine,
            "profile": profile,
            "regime": regime_name,
            "actual_profile": actual_profile,
        }

        try:
            engine = build_engine(target_engine)
            if ledger and not lightweight:
                ledger.record_intent("backtest_optimize", opt_ctx, input_hashes={})

            default_shrinkage = float(config.features.default_shrinkage_intensity)
            if actual_profile == "max_sharpe":
                default_shrinkage = max(default_shrinkage, 0.15)

            # CR-690: Adaptive Ridge Reloading
            current_ridge = default_shrinkage
            max_ridge_retries = 3
            ridge_attempt = 0
            final_flat_weights = pd.DataFrame()

            while ridge_attempt < max_ridge_retries:
                ridge_attempt += 1
                req = EngineRequest(
                    profile=actual_profile,
                    engine=target_engine,
                    regime=regime_name,
                    market_environment=market_env,
                    cluster_cap=0.25,
                    kappa_shrinkage_threshold=float(config.features.kappa_shrinkage_threshold),
                    default_shrinkage_intensity=current_ridge,
                    adaptive_fallback_profile=str(config.features.adaptive_fallback_profile),
                    benchmark_returns=bench_rets,
                    market_neutral=(actual_profile == "market_neutral"),
                )

                returns_for_opt = train_rets if actual_profile == "market" else train_rets_strat
                opt_resp = engine.optimize(returns=returns_for_opt, clusters=stringified_clusters, meta=window_meta, stats=self.stats, request=req)

                if is_meta:
                    flat_weights = opt_resp.weights
                else:
                    flat_weights = synthesizer.flatten_weights(opt_resp.weights)

                if not flat_weights.empty:
                    self._apply_diversity_constraints(flat_weights)

                if flat_weights.empty:
                    break

                # Verify with first simulator
                simulator = build_simulator(sim_names[0])
                state_key = f"{target_engine}_{sim_names[0]}_{profile}"
                last_state = current_holdings.get(state_key)
                sim_results = simulator.simulate(weights_df=flat_weights, returns=test_rets, initial_holdings=last_state)

                metrics = sim_results.get("metrics", sim_results) if isinstance(sim_results, dict) else getattr(sim_results, "metrics", {})
                sharpe = float(metrics.get("sharpe", 0.0))

                if sharpe > 10.0 and ridge_attempt < max_ridge_retries and actual_profile not in ["market", "benchmark"]:
                    current_ridge = 0.50 if ridge_attempt == 1 else 0.95
                    logger.warning(f"  [ADAPTIVE RIDGE] Window {window_index} ({actual_profile}) anomalous (Sharpe={sharpe:.2f}). Reloading Ridge: {current_ridge:.2f}")
                    continue

                if sharpe > 10.0 and actual_profile not in ["market", "benchmark"]:
                    logger.warning(f"  [WINDOW VETO] Window {window_index} ({actual_profile}) unstable. Forcing Equal Weight.")
                    flat_weights = self._get_equal_weight_flat(returns_for_opt, is_meta, synthesizer)

                final_flat_weights = flat_weights
                break

            if final_flat_weights.empty:
                return

            if ledger and not lightweight:
                weights_dict = final_flat_weights.set_index("Symbol")["Net_Weight"].to_dict()
                ledger.record_outcome(
                    step="backtest_optimize",
                    status="success",
                    output_hashes={},
                    metrics={"weights": weights_dict, "ridge_intensity": current_ridge, "ridge_attempts": ridge_attempt},
                    context=opt_ctx,
                )

            for sim_name in sim_names:
                self._run_simulation(
                    sim_name, target_engine, profile, window_index, final_flat_weights, test_rets, current_holdings, return_series, ledger, lightweight, config.features.selection_mode, results
                )

        except Exception as e:
            if ledger and not lightweight:
                ledger.record_outcome(step="backtest_optimize", status="error", output_hashes={}, metrics={"error": str(e)}, context=opt_ctx)

    def _apply_diversity_constraints(self, flat_weights: pd.DataFrame):
        w_sum_abs = flat_weights["Weight"].sum()
        if w_sum_abs > 0:
            flat_weights["Weight"] = flat_weights["Weight"].clip(upper=0.25 * w_sum_abs)
            flat_weights["Net_Weight"] = flat_weights["Net_Weight"].clip(lower=-0.25 * w_sum_abs, upper=0.25 * w_sum_abs)
            new_sum = flat_weights["Weight"].sum()
            if new_sum > 0:
                scale = w_sum_abs / new_sum
                flat_weights["Weight"] *= scale
                flat_weights["Net_Weight"] *= scale

    def _get_equal_weight_flat(self, returns_for_opt: pd.DataFrame, is_meta: bool, synthesizer: StrategySynthesizer) -> pd.DataFrame:
        n_strat = len(returns_for_opt.columns)
        if n_strat > 0:
            ew_weights = pd.Series(1.0 / n_strat, index=returns_for_opt.columns)
            dummy_weights = pd.DataFrame({"Symbol": ew_weights.index, "Weight": ew_weights.values})
            return dummy_weights if is_meta else synthesizer.flatten_weights(dummy_weights)
        return pd.DataFrame()

    def _run_simulation(
        self,
        sim_name: str,
        target_engine: str,
        profile: str,
        window_index: int,
        final_flat_weights: pd.DataFrame,
        test_rets: pd.DataFrame,
        current_holdings: dict[str, Any],
        return_series: dict[str, list[pd.Series]],
        ledger: AuditLedger,
        lightweight: bool,
        selection_mode: str,
        results: list[dict[str, Any]],
    ):
        sim_ctx = {
            "window_index": window_index,
            "engine": target_engine,
            "profile": profile,
            "simulator": sim_name,
            "selection_mode": selection_mode,
        }
        try:
            simulator = build_simulator(sim_name)
            if ledger and not lightweight:
                ledger.record_intent("backtest_simulate", sim_ctx, input_hashes={})

            state_key = f"{target_engine}_{sim_name}_{profile}"
            last_state = current_holdings.get(state_key)
            sim_results = simulator.simulate(weights_df=final_flat_weights, returns=test_rets, initial_holdings=last_state)

            if isinstance(sim_results, dict):
                current_holdings[state_key] = sim_results.get("final_holdings") or sim_results.get("final_weights")
            else:
                current_holdings[state_key] = getattr(sim_results, "final_holdings", getattr(sim_results, "final_weights", None))

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
                return_series.setdefault(key, []).append(daily_rets.clip(-1.0, 1.0))

            if ledger and not lightweight:
                data_payload = {"daily_returns": daily_rets.values.tolist() if isinstance(daily_rets, pd.Series) else (daily_rets if isinstance(daily_rets, list) else [])}
                if isinstance(daily_rets, pd.Series):
                    data_payload["ann_factor"] = _get_annualization_factor(daily_rets)
                ledger.record_outcome(step="backtest_simulate", status="success", output_hashes={}, metrics=sanitized_metrics, data=data_payload, context=sim_ctx)

            results.append({"window": window_index, "engine": target_engine, "profile": profile, "simulator": sim_name, "metrics": sanitized_metrics})
        except Exception as e:
            if ledger and not lightweight:
                ledger.record_outcome(step="backtest_simulate", status="error", output_hashes={}, metrics={"error": str(e)}, context=sim_ctx)

    def _save_tournament_artifacts(self, run_dir: Path, return_series: dict[str, list[pd.Series]]):
        returns_out = run_dir / "data" / "returns"
        returns_out.mkdir(parents=True, exist_ok=True)
        for key, series_list in return_series.items():
            if not series_list:
                continue
            try:
                full_series = pd.concat(series_list)
                full_series = full_series[~full_series.index.duplicated(keep="first")].sort_index()
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tournament Backtest Engine")
    parser.add_argument("--mode", choices=["production", "research"], default="research")
    parser.add_argument("--train-window", type=int)
    parser.add_argument("--test-window", type=int)
    parser.add_argument("--step-size", type=int)
    parser.add_argument("--run-id", help="Explicit run ID to use")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    from tradingview_scraper.settings import get_settings

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
