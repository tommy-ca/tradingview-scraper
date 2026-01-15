import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from tradingview_scraper.portfolio_engines import build_engine
from tradingview_scraper.portfolio_engines.backtest_simulators import build_simulator
from tradingview_scraper.portfolio_engines.base import EngineRequest, ProfileName
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.risk import AntifragilityAuditor
from tradingview_scraper.selection_engines import build_selection_engine
from tradingview_scraper.selection_engines.base import SelectionRequest, get_hierarchical_clusters
from tradingview_scraper.utils.audit import AuditLedger
from tradingview_scraper.utils.metrics import _get_annualization_factor
from tradingview_scraper.utils.synthesis import StrategySynthesizer

logger = logging.getLogger("backtest_engine")


def persist_tournament_artifacts(results: Dict[str, Any], output_dir: Path):
    """Saves tournament metrics and windows to disk for analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = output_dir / "tournament_results.json"
    try:
        with open(target_path, "w") as f:

            def _default(obj):
                if isinstance(obj, (pd.DataFrame, pd.Series)):
                    return {}
                if isinstance(obj, (np.integer, np.floating)):
                    return obj.item()
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return str(obj)

            json.dump(results, f, indent=2, default=_default)
    except Exception as e:
        logger.error(f"Failed to save tournament artifacts: {e}")


class BacktestOrchestrator:
    """
    Orchestrates the 3-pillar workflow: Selection -> Synthesis -> Allocation.
    """

    def __init__(self, engine: "BacktestEngine"):
        self.engine = engine
        self.config: Optional[Any] = None

    def resolve_regime_profile(self, regime: str) -> ProfileName:
        """Pillar 3: Map detected regime to the target risk profile."""
        mapping = {"EXPANSION": "max_sharpe", "INFLATIONARY_TREND": "barbell", "NORMAL": "max_sharpe", "STAGNATION": "min_variance", "TURBULENT": "hrp", "CRISIS": "hrp"}
        return cast(ProfileName, mapping.get(regime, "equal_weight"))


class BacktestEngine:
    """
    Unified Backtest Engine for Research and Production validation.
    """

    def __init__(self, lakehouse_dir: str = "data/lakehouse"):
        self.lakehouse = Path(lakehouse_dir)
        self.returns = pd.DataFrame()
        self.stats = pd.DataFrame()
        self.metadata = {}
        self.load_data()

        from tradingview_scraper.settings import get_settings

        settings = get_settings()
        self.detector = MarketRegimeDetector(audit_path=settings.summaries_run_dir / "regime_audit.jsonl")
        self.auditor = AntifragilityAuditor()
        self.orchestrator = BacktestOrchestrator(self)

    def load_data(self):
        from tradingview_scraper.settings import get_settings

        settings = get_settings()
        run_dir = settings.prepare_summaries_run_dir()

        # CR-831: Workspace Isolation
        # Prioritize run-specific artifacts
        default_rets = run_dir / "data" / "returns_matrix.parquet"
        default_meta = run_dir / "data" / "portfolio_meta.json"
        default_stats = run_dir / "data" / "antifragility_stats.json"

        rets_path = Path(os.getenv("RETURNS_MATRIX", str(default_rets)))
        # Fallback to shared lakehouse if run-specific doesn't exist
        if not rets_path.exists():
            rets_path = self.lakehouse / "returns_matrix.parquet"

        rets_path_pkl = self.lakehouse / "portfolio_returns.pkl"

        stats_path = Path(os.getenv("ANTIFRAGILITY_STATS", str(default_stats)))
        if not stats_path.exists():
            stats_path = self.lakehouse / "antifragility_stats.parquet"

        stats_path_json = self.lakehouse / "antifragility_stats.json"

        meta_path = Path(os.getenv("PORTFOLIO_META", str(default_meta)))
        if not meta_path.exists():
            meta_path = self.lakehouse / "portfolio_meta.json"
        if not meta_path.exists():
            meta_path = self.lakehouse / "portfolio_candidates.json"

        # Prioritize run-specific matrix
        if rets_path.exists() and rets_path.suffix == ".parquet":
            self.returns = pd.read_parquet(rets_path)
        elif rets_path_pkl.exists():
            self.returns = pd.read_pickle(rets_path_pkl)
        elif rets_path.exists():
            self.returns = pd.read_pickle(rets_path)

        if stats_path.exists():
            if stats_path.suffix == ".parquet":
                self.stats = pd.read_parquet(stats_path)
            else:
                self.stats = pd.read_json(stats_path)
        elif stats_path_json.exists():
            self.stats = pd.read_json(stats_path_json)
            if "Symbol" in self.stats.columns:
                self.stats.set_index("Symbol", inplace=True)

        if meta_path.exists():
            with open(meta_path, "r") as f:
                raw_meta = json.load(f)
                if isinstance(raw_meta, dict):
                    # Handle portfolio_meta.json dictionary format
                    self.metadata = {}
                    for s, m in raw_meta.items():
                        if isinstance(m, dict):
                            m["symbol"] = s
                            self.metadata[s] = m
                elif isinstance(raw_meta, list):
                    # Handle portfolio_candidates.json list format
                    self.metadata = {c["symbol"]: c for c in raw_meta if "symbol" in c}

    def run_tournament(self, **kwargs) -> Dict:
        print("DEBUG: run_tournament called")
        from tradingview_scraper.settings import get_settings

        config = get_settings()
        self.orchestrator.config = config
        train_window = kwargs.get("train_window") or int(config.train_window)
        test_window = kwargs.get("test_window") or int(config.test_window)
        step_size = kwargs.get("step_size") or int(config.step_size)
        profiles = kwargs.get("profiles") or [p.strip() for p in config.profiles.split(",")]
        engines = kwargs.get("engines") or [e.strip() for e in config.engines.split(",")]
        sim_names = kwargs.get("simulators") or [s.strip() for s in config.backtest_simulators.split(",")]
        selection_mode_override = kwargs.get("selection_mode")
        regime_weights = kwargs.get("regime_weights")

        returns_to_use = self.returns.dropna(how="all")
        total_len = len(returns_to_use)
        logger.info(f"Tournament Started: {total_len} rows available.")

        # Pillar 2: Synthesis Layer Initialization
        synthesizer = StrategySynthesizer()

        # Update detector if weights are provided
        detector_to_use = self.detector
        if regime_weights:
            detector_to_use = MarketRegimeDetector(weights=regime_weights)

        run_dir = config.prepare_summaries_run_dir()
        ledger = AuditLedger(run_dir) if config.features.feat_audit_ledger else None

        if ledger and not ledger.last_hash:
            manifest_hash = hashlib.sha256(open(config.manifest_path, "rb").read()).hexdigest() if config.manifest_path.exists() else "unknown"
            audit_config = {
                "train_window": train_window,
                "test_window": test_window,
                "step_size": step_size,
                "selection_mode": selection_mode_override or str(config.features.selection_mode or "v3.4"),
                "feature_lookback": int(config.features.feature_lookback),
                "profiles": profiles,
                "engines": engines,
                "simulators": sim_names,
            }
            ledger.record_genesis(config.run_id, config.profile, manifest_hash, config=audit_config)

        results = []
        # Prepare return series accumulator
        return_series: Dict[str, List[pd.Series]] = {}

        for i in range(train_window, total_len - test_window, step_size):
            # Pillar 1: High-Precision Window Slicing (CR-185)
            # train_rets: [i-train_window, i) -> Data up to but excluding 'today'
            # test_rets: [i, i+test_window) -> Realized returns starting 'today'
            train_rets = returns_to_use.iloc[i - train_window : i]
            test_rets = returns_to_use.iloc[i : i + test_window]

            if train_rets.empty or test_rets.empty:
                continue

            # 1. Market Regime detection
            regime_resp = detector_to_use.detect_regime(train_rets)
            regime_name = regime_resp[0]
            logger.info(f"Window {i}: Regime: {regime_name}")

            # Strategy Intent Filter (CR-820): Restrict pool to active manifest strategies
            active_strategies = set((config.discovery.get("strategies") or {}).keys())

            logger.info(f"DEBUG: Active Strategies: {active_strategies}")

            raw_cands = []
            for k, v in self.metadata.items():
                if k not in train_rets.columns:
                    continue

                # If manifest defines specific strategies, filter the recruitment pool
                if active_strategies:
                    atom_logic = v.get("logic")
                    if atom_logic not in active_strategies:
                        # logger.info(f"DEBUG: Filtering {k} - logic {atom_logic} not in {active_strategies}")
                        continue

                raw_cands.append(v)

            logger.info(f"DEBUG: Window {i} Pool Size: {len(raw_cands)}")
            if len(raw_cands) > 0:
                logics = sorted(list(set(c.get("logic") for c in raw_cands)))
                logger.info(f"DEBUG: Pool Logics: {logics}")

            current_mode = selection_mode_override or str(config.features.selection_mode or "v3.4")
            selection_engine = build_selection_engine(current_mode)

            sel_req = SelectionRequest(threshold=float(config.threshold), top_n=int(config.top_n), min_momentum_score=float(config.min_momentum_score), max_clusters=25)
            selection = selection_engine.select(train_rets, raw_cands, self.stats, sel_req)
            if selection is None:
                continue

            winners_syms = [w["symbol"] for w in selection.winners]
            window_meta = self.metadata.copy()
            for w in selection.winners:
                window_meta[w["symbol"]] = w

            if ledger:
                # CR-420: Structured Telemetry Segregation
                # Extract pipeline audit from metrics to keep scalar KPIs clean
                metrics_payload = {
                    "n_universe_symbols": len(self.returns.columns),
                    "n_refinement_candidates": len(train_rets.columns),
                    "n_discovery_candidates": len(raw_cands),
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

            if not winners_syms:
                continue

            # 3. Pillar 2: Strategy Synthesis
            # Applies alpha logic and handles SHORT inversion
            train_rets_strat = synthesizer.synthesize(train_rets, selection.winners, config.features)

            # 4. Pillar 3: Allocation (Tournament)

            # Re-calculate clusters on synthesized returns (CR-291)
            # This identifies uncorrelated alpha clusters in logic-space
            new_cluster_ids, _ = get_hierarchical_clusters(train_rets_strat, float(config.threshold), 25)
            stringified_clusters = {}
            for sym, c_id in zip(train_rets_strat.columns, new_cluster_ids):
                stringified_clusters.setdefault(str(c_id), []).append(str(sym))

            # Benchmark for market-neutral
            bench_sym = config.benchmark_symbols[0] if config.benchmark_symbols else None
            bench_rets = train_rets[bench_sym] if bench_sym and bench_sym in train_rets.columns else None

            for engine_name in engines:
                # Optimized Path: Adaptive engine only needs to run once per window
                profiles_to_run = ["adaptive"] if engine_name == "adaptive" else profiles

                for profile in profiles_to_run:
                    actual_profile = self.orchestrator.resolve_regime_profile(regime_name) if profile == "adaptive" else cast(ProfileName, profile)

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

                        # Hardened Ridge for MaxSharpe (CR-600)
                        default_shrinkage = float(config.features.default_shrinkage_intensity)
                        if actual_profile == "max_sharpe":
                            default_shrinkage = max(default_shrinkage, 0.15)

                        req = EngineRequest(
                            profile=actual_profile,
                            engine=target_engine,
                            regime=regime_name,
                            market_environment=regime_name,
                            cluster_cap=0.25,
                            kappa_shrinkage_threshold=float(config.features.kappa_shrinkage_threshold),
                            default_shrinkage_intensity=default_shrinkage,
                            adaptive_fallback_profile=str(config.features.adaptive_fallback_profile),
                            benchmark_returns=bench_rets,  # For market_neutral
                            market_neutral=(actual_profile == "market_neutral"),
                        )

                        # Market profile needs the full pool, others use synthesized strategies
                        returns_for_opt = train_rets if actual_profile == "market" else train_rets_strat

                        opt_resp = engine.optimize(returns=returns_for_opt, clusters=stringified_clusters, meta=window_meta, stats=self.stats, request=req)

                        # Execution Layer: Aggregates strategy-level weights back to physical assets
                        flat_weights = synthesizer.flatten_weights(opt_resp.weights)

                        # Pillar 3: Weight Flattening Guard (Phase 125)
                        # Verifies that aggregated net exposure matches target intent
                        if not flat_weights.empty:
                            net_sum = float(flat_weights["Net_Weight"].sum())
                            gross_sum = float(flat_weights["Weight"].sum())
                            # Market Neutral profiles (CR-290) should have net exposure near 0
                            # Standard long-biased profiles should have net exposure near 1.0
                            is_neutral = actual_profile == "market_neutral" or getattr(req, "market_neutral", False)
                            target_net = 0.0 if is_neutral else 1.0

                            if is_neutral:
                                if abs(net_sum) > 0.15:
                                    logger.warning(f"Weight Guard Triggered (Neutral): Profile={actual_profile}, Net={net_sum:.4f}, Target={target_net:.4f}")
                                else:
                                    logger.info(f"Weight Guard Passed (Neutral): Profile={actual_profile}, Net={net_sum:.4f}")
                            else:
                                if net_sum < 0.5:
                                    logger.warning(f"Weight Guard Triggered (Low Exposure): Profile={actual_profile}, Net={net_sum:.4f}, Gross={gross_sum:.4f}")
                                else:
                                    logger.info(f"Weight Guard Passed: Profile={actual_profile}, Net={net_sum:.4f}, Gross={gross_sum:.4f}")

                        if ledger:
                            weights_dict = flat_weights.set_index("Symbol")["Net_Weight"].to_dict()
                            ledger.record_outcome(step="backtest_optimize", status="success", output_hashes={}, metrics={"weights": weights_dict}, context=opt_ctx)

                        if flat_weights.empty:
                            continue

                        # 5. Simulation
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

                                # Simulator MUST use original test returns of physical assets
                                sim_results = simulator.simulate(weights_df=flat_weights, returns=test_rets)

                                metrics = {}
                                if isinstance(sim_results, dict):
                                    metrics = sim_results.get("metrics", sim_results)
                                elif hasattr(sim_results, "metrics"):
                                    metrics = getattr(sim_results, "metrics", {})

                                sanitized_metrics = {}
                                for k, v in metrics.items():
                                    if isinstance(v, (int, float, np.number, str, bool, type(None))):
                                        sanitized_metrics[k] = float(v) if isinstance(v, (np.number, float, int)) else v

                                # Persistent Return Storage (CR-810)
                                # Decoupled from ledger to ensure meta-allocation availability
                                daily_rets = metrics.get("daily_returns")
                                if isinstance(daily_rets, pd.Series):
                                    key = f"{target_engine}_{sim_name}_{profile}"
                                    if key not in return_series:
                                        return_series[key] = []
                                    return_series[key].append(daily_rets)

                                if ledger:
                                    # CR-750: Capture daily returns for independent verification
                                    # We move structured data to 'data' and keep metrics for scalars
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
        # We want to save to the RUN directory created for this tournament.
        returns_out = run_dir / "data" / "returns"
        returns_out.mkdir(parents=True, exist_ok=True)
        for key, series_list in return_series.items():
            if not series_list:
                continue
            try:
                # Type safe concatenation for Series
                full_series_raw = pd.concat(series_list)
                if isinstance(full_series_raw, pd.Series):
                    # Handle overlaps if any
                    full_series = full_series_raw[~full_series_raw.index.duplicated(keep="first")]
                    if hasattr(full_series, "sort_index"):
                        full_series = getattr(full_series, "sort_index")()
                    out_path = returns_out / f"{key}.pkl"
                    full_series.to_pickle(str(out_path))
                    logger.info(f"Saved stitched returns to {out_path}")
            except Exception as e:
                logger.error(f"Failed to save returns for {key}: {e}")

        return {"results": results}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tournament Backtest Engine")
    parser.add_argument("--mode", choices=["production", "research"], default="research")
    parser.add_argument("--train-window", type=int)
    parser.add_argument("--test-window", type=int)
    parser.add_argument("--step-size", type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    engine = BacktestEngine()
    tournament_results = engine.run_tournament(mode=args.mode, train_window=args.train_window, test_window=args.test_window, step_size=args.step_size)

    from tradingview_scraper.settings import get_settings

    config = get_settings()
    run_dir = config.prepare_summaries_run_dir()
    persist_tournament_artifacts(tournament_results, run_dir / "data")

    print("\n" + "=" * 50)
    print("TOURNAMENT COMPLETE")
    print("=" * 50)
