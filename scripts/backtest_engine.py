import argparse
import datetime
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, cast

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from tradingview_scraper.portfolio_engines.backtest_simulators import build_simulator
from tradingview_scraper.portfolio_engines.base import EngineRequest, ProfileName
from tradingview_scraper.portfolio_engines.engines import build_engine
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.risk import AntifragilityAuditor
from tradingview_scraper.selection_engines.base import SelectionRequest
from tradingview_scraper.selection_engines.engines import SelectionEngineV3_2
from tradingview_scraper.utils.audit import AuditLedger

logger = logging.getLogger("backtest_engine")


class BacktestEngine:
    """
    Unified Backtest Engine for Research and Production validation.
    Orchestrates selection, optimization, and simulation across windows.
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

    def load_data(self):
        rets_path = self.lakehouse / "returns_matrix.parquet"
        stats_path = self.lakehouse / "antifragility_stats.parquet"
        meta_path = self.lakehouse / "portfolio_candidates.json"

        if rets_path.exists():
            self.returns = pd.read_parquet(rets_path)
        if stats_path.exists():
            self.stats = pd.read_parquet(stats_path)
        if meta_path.exists():
            with open(meta_path, "r") as f:
                raw_meta = json.load(f)
                self.metadata = {c["symbol"]: c for c in raw_meta}

    def run_tournament(self, **kwargs) -> Dict:
        from tradingview_scraper.settings import get_settings

        config = get_settings()
        train_window = kwargs.get("train_window") or int(config.train_window)
        test_window = kwargs.get("test_window") or int(config.test_window)
        step_size = kwargs.get("step_size") or int(config.step_size)
        profiles = kwargs.get("profiles") or [p.strip() for p in config.profiles.split(",")]
        engines = kwargs.get("engines") or [e.strip() for e in config.engines.split(",")]
        sim_names = kwargs.get("simulators") or [s.strip() for s in config.backtest_simulators.split(",")]

        returns_to_use = self.returns.dropna(how="all")
        total_len = len(returns_to_use)

        run_dir = config.prepare_summaries_run_dir()
        ledger = AuditLedger(run_dir) if config.features.feat_audit_ledger else None

        # Record Genesis if ledger is new
        if ledger and not ledger.last_hash:
            manifest_hash = hashlib.sha256(open(config.manifest_path, "rb").read()).hexdigest() if config.manifest_path.exists() else "unknown"
            ledger.record_genesis(config.run_id, config.profile, manifest_hash)

        # 1. Rolling Windows
        results = []
        for i in range(train_window, total_len - test_window, step_size):
            window_start = returns_to_use.index[i - train_window]
            window_end = returns_to_use.index[i]
            test_end = returns_to_use.index[i + test_window]

            train_rets = returns_to_use.loc[window_start:window_end]
            test_rets = returns_to_use.loc[window_end:test_end]

            # 2. Market Regime detection
            # detector returns a MarketRegimeResponse (regime, score, quadrant)
            regime_resp = self.detector.detect_regime(train_rets)
            regime_name = regime_resp.regime
            logger.info(f"Window {i}: Regime: {regime_name}")

            # 3. Dynamic Selection (Operation Darwin)
            selection_engine = SelectionEngineV3_2()
            raw_cands = [v for k, v in self.metadata.items() if k in train_rets.columns]

            # Record Selection Intent
            if ledger:
                ledger.record_intent("backtest_select", {"window_index": i, "engine": selection_engine.name}, input_hashes={})

            sel_req = SelectionRequest(
                threshold=0.45,
                top_n=int(config.top_n),
                min_momentum_score=float(config.min_momentum_score),
                max_clusters=25,
            )
            selection = selection_engine.select(train_rets, raw_cands, self.stats, sel_req)
            winners = [w["symbol"] for w in selection.winners]

            # Record Selection Outcome
            if ledger:
                ledger.record_outcome(
                    step="backtest_select",
                    status="success",
                    output_hashes={},
                    metrics={"n_winners": len(winners), "winners": winners, **selection.metrics},
                )

            if not winners:
                logger.warning(f"No winners selected for window {i}")
                continue

            # 4. Optimization Tournament
            for engine_name in engines:
                for profile in profiles:
                    try:
                        engine = build_engine(engine_name)

                        # Record Optimization Intent
                        if ledger:
                            ledger.record_intent("backtest_optimize", {"window_index": i, "engine": engine_name, "profile": profile, "regime": regime_name}, input_hashes={})

                        req = EngineRequest(
                            profile=cast(ProfileName, profile),
                            regime=regime_name,
                            market_environment=regime_name,
                            cluster_cap=0.25,
                        )

                        # Ensure cluster IDs are strings for the engine
                        stringified_clusters = {str(k): v for k, v in selection.audit_clusters.items()}

                        opt_resp = engine.optimize(returns=train_rets[winners], clusters=stringified_clusters, meta=self.metadata, stats=self.stats, request=req)

                        # Record Optimization Outcome
                        if ledger:
                            weights_dict = opt_resp.weights.set_index("Symbol")["Weight"].to_dict() if not opt_resp.weights.empty else {}
                            ledger.record_outcome(step="backtest_optimize", status="success", output_hashes={}, metrics={"weights": weights_dict})

                        # 5. Simulation
                        for sim_name in sim_names:
                            simulator = build_simulator(sim_name)

                            if ledger:
                                ledger.record_intent(
                                    "backtest_simulate",
                                    {"window_index": i, "engine": engine_name, "profile": profile, "simulator": sim_name},
                                    input_hashes={},
                                )

                            sim_results = simulator.simulate(weights_df=opt_resp.weights, returns=test_rets)

                            # simulator.simulate returns a dict with metrics
                            metrics = sim_results.get("metrics", {}) if isinstance(sim_results, dict) else {}

                            if ledger:
                                ledger.record_outcome(step="backtest_simulate", status="success", output_hashes={}, metrics=metrics)

                            results.append({"window": i, "engine": engine_name, "profile": profile, "simulator": sim_name, "metrics": metrics})
                    except Exception as e:
                        logger.error(f"Error in tournament window {i}, engine {engine_name}, profile {profile}: {e}")
                        if ledger:
                            ledger.record_outcome(step="backtest_optimize", status="error", output_hashes={}, metrics={"error": str(e)})

        return {"tournament_results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="research", choices=["research", "production"])
    parser.add_argument("--profile", default="crypto_production")
    parser.add_argument("--train-window", type=int)
    parser.add_argument("--test-window", type=int)
    parser.add_argument("--step-size", type=int)
    args = parser.parse_args()

    # Set TV_RUN_ID for proper directory creation
    os.environ.setdefault("TV_RUN_ID", datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

    logging.basicConfig(level=logging.INFO)
    engine = BacktestEngine()
    engine.run_tournament(train_window=args.train_window, test_window=args.test_window, step_size=args.step_size)
