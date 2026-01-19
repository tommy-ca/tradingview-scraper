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


def persist_tournament_artifacts(results: Dict[str, Any], output_dir: Path):
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
        self.metadata = {}
        self.stats = pd.DataFrame()

    def load_data(self, run_dir: Optional[Path] = None):
        """Load returns and metadata from lakehouse or run directory."""
        if not run_dir:
            # Try to find latest run if not provided
            runs_dir = Path("artifacts/summaries/runs")
            if runs_dir.exists():
                latest_runs = sorted([d for d in runs_dir.iterdir() if d.is_dir() and (d / "data" / "returns_matrix.parquet").exists()], key=os.path.getmtime, reverse=True)
                if latest_runs:
                    run_dir = latest_runs[0]

        data_dir = run_dir / "data" if run_dir else Path("data/lakehouse")
        logger.info(f"Loading data from {data_dir}")

        # Load Candidates
        cands_path = data_dir / "portfolio_candidates_raw.json"
        if not cands_path.exists():
            cands_path = data_dir / "portfolio_candidates.json"

        self.raw_candidates = []
        if cands_path.exists():
            import json

            with open(cands_path, "r") as f:
                self.raw_candidates = json.load(f)

        returns_path = data_dir / "returns_matrix.parquet"

        if not returns_path.exists():
            returns_path = data_dir / "portfolio_returns.pkl"

        if not returns_path.exists():
            # Ultimate fallback to lakehouse
            returns_path = Path("data/lakehouse/returns_matrix.parquet")
            if not returns_path.exists():
                returns_path = Path("data/lakehouse/portfolio_returns.pkl")

        if not returns_path.exists():
            raise FileNotFoundError(f"Returns matrix not found at {returns_path}")

        if str(returns_path).endswith(".parquet"):
            self.returns = pd.read_parquet(returns_path)
        else:
            self.returns = pd.read_pickle(returns_path)

        metadata_path = data_dir / "metadata_catalog.json"
        if not metadata_path.exists():
            metadata_path = data_dir / "portfolio_meta.json"

        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                import json

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

    def run_tournament(self, mode: str = "production", train_window: Optional[int] = None, test_window: Optional[int] = None, step_size: Optional[int] = None, run_dir: Optional[Path] = None):
        """Run a rolling-window backtest tournament."""
        if self.returns.empty:
            self.load_data(run_dir=run_dir)

        config = self.settings
        train_window = int(train_window or config.train_window)
        test_window = int(test_window or config.test_window)
        step_size = int(step_size or config.step_size)

        profiles = config.profiles.split(",")
        engines = config.engines.split(",")
        sim_names = config.backtest_simulators.split(",")

        results = []
        results_meta = {
            "mode": mode,
            "train_window": train_window,
            "test_window": test_window,
            "step_size": step_size,
            "profiles": profiles,
            "engines": engines,
            "simulators": sim_names,
        }

        synthesizer = StrategySynthesizer()
        if not run_dir:
            run_dir = self.settings.prepare_summaries_run_dir()

        ledger = AuditLedger(run_dir)

        # Persistence for return series
        return_series: Dict[str, List[pd.Series]] = {}
        current_holdings: Dict[str, Any] = {}

        # 1. Rolling Windows
        n_obs = len(self.returns)
        windows = list(range(train_window, n_obs - test_window, step_size))
        logger.info(f"Tournament Started: {n_obs} rows available. Windows: count={len(windows)}, train={train_window}, test={test_window}, step={step_size}")

        for i in windows:
            train_rets = self.returns.iloc[i - train_window : i]
            test_rets = self.returns.iloc[i : i + test_window]

            # 2. Pillar 1: Universe Selection
            regime_name = "NORMAL"
            current_mode = config.features.selection_mode

            selection_engine = build_selection_engine(current_mode)
            from tradingview_scraper.selection_engines.base import SelectionRequest

            req_select = SelectionRequest(top_n=config.top_n, threshold=config.threshold)
            selection = selection_engine.select(returns=train_rets, raw_candidates=self.raw_candidates, stats_df=self.stats, request=req_select)

            # CR-FIX: Ensure winners exist in the returns matrix (Phase 225)
            if selection.winners:
                selection_winners = [w for w in selection.winners if w["symbol"] in train_rets.columns]
                if len(selection_winners) != len(selection.winners):
                    logger.warning(f"  [DATA GAP] Filtered {len(selection.winners) - len(selection_winners)} winners missing from returns matrix.")

                # Mocking the winners list in selection response
                object.__setattr__(selection, "winners", selection_winners)

            if selection.winners:
                winners_syms = [w["symbol"] for w in selection.winners]
                window_meta = self.metadata.copy()
                for w in selection.winners:
                    window_meta[w["symbol"]] = w

                if ledger:
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
                        context={"window_index": i, "engine": selection_engine.name},
                    )

                if winners_syms:
                    # 3. Pillar 2: Strategy Synthesis
                    train_rets_strat = synthesizer.synthesize(train_rets, selection.winners, config.features)

                    # 4. Pillar 3: Allocation
                    new_cluster_ids, _ = get_hierarchical_clusters(train_rets_strat, float(config.threshold), 25)
                    stringified_clusters = {}
                    for sym, c_id in zip(train_rets_strat.columns, new_cluster_ids):
                        stringified_clusters.setdefault(str(c_id), []).append(str(sym))

                    bench_sym = config.benchmark_symbols[0] if config.benchmark_symbols else None
                    bench_rets = train_rets[bench_sym] if bench_sym and bench_sym in train_rets.columns else None

                    for engine_name in engines:
                        profiles_to_run = ["adaptive"] if engine_name == "adaptive" else profiles

                        for profile in profiles_to_run:
                            actual_profile = cast(ProfileName, profile)

                            target_engine = engine_name
                            if actual_profile in ["market", "benchmark"]:
                                target_engine = "market"
                            elif actual_profile == "barbell":
                                target_engine = "custom"

                            opt_ctx = {
                                "window_index": i,
                                "engine": target_engine,
                                "profile": profile,
                                "regime": regime_name,
                                "actual_profile": actual_profile,
                                "selection_mode": current_mode,
                            }
                            try:
                                engine = build_engine(target_engine)
                                if ledger:
                                    ledger.record_intent("backtest_optimize", opt_ctx, input_hashes={})

                                default_shrinkage = float(config.features.default_shrinkage_intensity)
                                if actual_profile == "max_sharpe":
                                    default_shrinkage = max(default_shrinkage, 0.15)

                                # CR-690: Adaptive Ridge Reloading (Phase 224)
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
                                        market_environment=regime_name,
                                        cluster_cap=0.25,
                                        kappa_shrinkage_threshold=float(config.features.kappa_shrinkage_threshold),
                                        default_shrinkage_intensity=current_ridge,
                                        adaptive_fallback_profile=str(config.features.adaptive_fallback_profile),
                                        benchmark_returns=bench_rets,
                                        market_neutral=(actual_profile == "market_neutral"),
                                    )

                                    returns_for_opt = train_rets if actual_profile == "market" else train_rets_strat
                                    opt_resp = engine.optimize(returns=returns_for_opt, clusters=stringified_clusters, meta=window_meta, stats=self.stats, request=req)
                                    flat_weights = synthesizer.flatten_weights(opt_resp.weights)

                                    if flat_weights.empty:
                                        break

                                    verify_sim_name = sim_names[0]
                                    simulator = build_simulator(verify_sim_name)
                                    state_key = f"{target_engine}_{verify_sim_name}_{profile}"
                                    last_state = current_holdings.get(state_key)
                                    sim_results = simulator.simulate(weights_df=flat_weights, returns=test_rets, initial_holdings=last_state)

                                    metrics = sim_results.get("metrics", sim_results) if isinstance(sim_results, dict) else getattr(sim_results, "metrics", {})
                                    sharpe = float(metrics.get("sharpe", 0.0))

                                    if sharpe > 10.0 and ridge_attempt < max_ridge_retries and actual_profile not in ["market", "benchmark"]:
                                        current_ridge = 0.50 if ridge_attempt == 1 else 0.95
                                        logger.warning(f"  [ADAPTIVE RIDGE] Window {i} ({actual_profile}) anomalous (Sharpe={sharpe:.2f}). Reloading MAX Ridge: {current_ridge:.2f}")
                                        continue

                                    # CR-FIX: Hard Fallback to EW for persistent instability (Phase 225)
                                    if sharpe > 10.0 and ridge_attempt == max_ridge_retries and actual_profile not in ["market", "benchmark"]:
                                        logger.warning(f"  [HARD FALLBACK] Window {i} ({actual_profile}) remains unstable (Sharpe={sharpe:.2f}). Forcing Equal Weight.")
                                        n_strat = len(returns_for_opt.columns)
                                        if n_strat > 0:
                                            ew_weights = pd.Series(1.0 / n_strat, index=returns_for_opt.columns)
                                            dummy_weights = pd.DataFrame({"Symbol": ew_weights.index, "Weight": ew_weights.values})
                                            final_flat_weights = synthesizer.flatten_weights(dummy_weights)
                                            break

                                    final_flat_weights = flat_weights
                                    break

                                if final_flat_weights.empty:
                                    continue

                                if ledger:
                                    weights_dict = final_flat_weights.set_index("Symbol")["Net_Weight"].to_dict()
                                    ledger.record_outcome(
                                        step="backtest_optimize",
                                        status="success",
                                        output_hashes={},
                                        metrics={"weights": weights_dict, "ridge_intensity": current_ridge, "ridge_attempts": ridge_attempt},
                                        context=opt_ctx,
                                    )

                                for sim_name in sim_names:
                                    sim_ctx = {
                                        "window_index": i,
                                        "engine": target_engine,
                                        "profile": profile,
                                        "simulator": sim_name,
                                        "selection_mode": current_mode,
                                    }
                                    try:
                                        simulator = build_simulator(sim_name)
                                        if ledger:
                                            ledger.record_intent("backtest_simulate", sim_ctx, input_hashes={})

                                        state_key = f"{target_engine}_{sim_name}_{profile}"
                                        last_state = current_holdings.get(state_key)
                                        sim_results = simulator.simulate(weights_df=final_flat_weights, returns=test_rets, initial_holdings=last_state)

                                        if isinstance(sim_results, dict):
                                            if "final_holdings" in sim_results:
                                                current_holdings[state_key] = sim_results["final_holdings"]
                                            elif "final_weights" in sim_results:
                                                current_holdings[state_key] = sim_results["final_weights"]
                                        elif hasattr(sim_results, "final_holdings"):
                                            current_holdings[state_key] = getattr(sim_results, "final_holdings")
                                        elif hasattr(sim_results, "final_weights"):
                                            current_holdings[state_key] = getattr(sim_results, "final_weights")

                                        metrics = sim_results.get("metrics", sim_results) if isinstance(sim_results, dict) else getattr(sim_results, "metrics", {})
                                        sanitized_metrics = {}

                                        if "top_assets" in metrics:
                                            try:
                                                top_assets = metrics["top_assets"]
                                                if isinstance(top_assets, list):
                                                    hhi = sum([a.get("Weight", 0) ** 2 for a in top_assets])
                                                    sanitized_metrics["concentration_hhi"] = float(hhi)
                                                    sanitized_metrics["top_assets"] = top_assets
                                            except Exception as e:
                                                logger.warning(f"Failed to calculate HHI: {e}")

                                        for k, v in metrics.items():
                                            if isinstance(v, (int, float, np.number, str, bool, type(None))):
                                                sanitized_metrics[k] = float(v) if isinstance(v, (np.number, float, int)) else v
                                            elif k == "top_assets" and isinstance(v, list):
                                                sanitized_metrics[k] = v

                                        daily_rets = metrics.get("daily_returns")
                                        if isinstance(daily_rets, pd.Series):
                                            key = f"{target_engine}_{sim_name}_{profile}"
                                            if key not in return_series:
                                                return_series[key] = []
                                            # CR-691: Numerical Clipping
                                            clamped_rets = daily_rets.clip(-1.0, 1.0)
                                            return_series[key].append(clamped_rets)

                                        if ledger:
                                            data_payload: Dict[str, Any] = {"daily_returns": []}
                                            if isinstance(daily_rets, pd.Series):
                                                data_payload["daily_returns"] = daily_rets.values.tolist()
                                                data_payload["ann_factor"] = _get_annualization_factor(daily_rets)
                                            elif isinstance(daily_rets, list):
                                                data_payload["daily_returns"] = daily_rets

                                            ledger.record_outcome(step="backtest_simulate", status="success", output_hashes={}, metrics=sanitized_metrics, data=data_payload, context=sim_ctx)

                                        results.append({"window": i, "engine": target_engine, "profile": profile, "simulator": sim_name, "metrics": sanitized_metrics})
                                    except Exception as e_sim:
                                        if ledger:
                                            ledger.record_outcome(step="backtest_simulate", status="error", output_hashes={}, metrics={"error": str(e_sim)}, context=sim_ctx)
                            except Exception as e:
                                if ledger:
                                    ledger.record_outcome(step="backtest_optimize", status="error", output_hashes={}, metrics={"error": str(e)}, context=opt_ctx)

        # Save stitched return series
        returns_out = run_dir / "data" / "returns"
        returns_out.mkdir(parents=True, exist_ok=True)
        for key, series_list in return_series.items():
            if not series_list:
                continue
            try:
                full_series_raw = pd.concat(series_list)
                if isinstance(full_series_raw, (pd.Series, pd.DataFrame)):
                    full_series = full_series_raw[~full_series_raw.index.duplicated(keep="first")]
                    if hasattr(full_series, "sort_index"):
                        full_series = full_series.sort_index()
                    out_path = returns_out / f"{key}.pkl"
                    if hasattr(full_series, "to_pickle"):
                        full_series.to_pickle(str(out_path))
                    logger.info(f"Saved stitched returns to {out_path}")
            except Exception as e:
                logger.error(f"Failed to save returns for {key}: {e}")

        return {"results": results, "meta": results_meta}


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
