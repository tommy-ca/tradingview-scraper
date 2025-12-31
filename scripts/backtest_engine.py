import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

# Add the project root to the path so we can import internal modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingview_scraper.portfolio_engines.backtest_simulators import build_simulator
from tradingview_scraper.portfolio_engines.base import EngineRequest, EngineUnavailableError, ProfileName
from tradingview_scraper.portfolio_engines.engines import build_engine, list_available_engines, list_known_engines
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.risk import AntifragilityAuditor
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash  # type: ignore

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backtest_engine")


class BacktestEngine:
    def __init__(self, returns_path: str = "data/lakehouse/portfolio_returns.pkl"):
        if not os.path.exists(returns_path):
            raise FileNotFoundError(f"Returns matrix missing: {returns_path}")

        # Explicitly cast to DataFrame to satisfy linter
        with open(returns_path, "rb") as f_in:
            self.returns = cast(pd.DataFrame, pd.read_pickle(f_in))

        # Load raw candidates for dynamic selection
        self.raw_candidates = []
        raw_path = "data/lakehouse/portfolio_candidates_raw.json"
        if os.path.exists(raw_path):
            with open(raw_path, "r") as f:
                self.raw_candidates = json.load(f)

        self.detector = MarketRegimeDetector()

    def _load_initial_state(self) -> Dict[str, pd.Series]:
        """Loads the last implemented state from portfolio_actual_state.json."""
        state_path = "data/lakehouse/portfolio_actual_state.json"
        if not os.path.exists(state_path):
            return {}

        try:
            with open(state_path, "r") as f:
                state = json.load(f)

            initial_holdings = {}
            for profile, data in state.items():
                assets = data.get("assets", [])
                if not assets:
                    continue
                w_series = pd.Series({a["Symbol"]: float(a.get("Weight", 0.0)) for a in assets})
                initial_holdings[profile] = w_series
            return initial_holdings
        except Exception as e:
            logger.warning(f"Failed to load initial state: {e}")
            return {}

    def run_walk_forward(
        self,
        train_window: int = 120,
        test_window: int = 20,
        step_size: int = 20,
        profile: str = "risk_parity",
        engine: str = "custom",
        cluster_cap: float = 0.25,
        simulator_name: str = "custom",
    ):
        logger.info(f"Starting Walk-Forward Backtest (Engine: {engine}, Profile: {profile}, Simulator: {simulator_name})")
        simulator = build_simulator(simulator_name)

        results = []
        cumulative_returns = pd.Series(dtype=float)
        prev_w_series = pd.Series(dtype=float)

        total_len = len(self.returns)
        if total_len < train_window + test_window:
            return None

        for start_idx in range(0, total_len - train_window - test_window + 1, step_size):
            train_end = start_idx + train_window
            train_data = self.returns.iloc[start_idx:train_end]
            test_data = self.returns.iloc[train_end : train_end + test_window]
            regime = self.detector.detect_regime(train_data)[0]

            clusters = self._cluster_data(train_data)
            stats_df = self._audit_training_stats(train_data)

            try:
                weights_df = self._compute_weights(train_data, clusters, stats_df, profile, engine, cluster_cap, {}, cast(pd.Series, prev_w_series), regime)
            except Exception as e:
                logger.error(f"Error computing weights: {e}")
                continue

            if weights_df.empty:
                continue

            test_perf = simulator.simulate(test_data, weights_df)
            prev_w_series = weights_df.set_index("Symbol")["Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"].astype(float)

            window_res = {
                "engine": engine,
                "profile": profile,
                "start_date": str(test_data.index[0]),
                "end_date": str(test_data.index[-1]),
                "regime": self.detector.detect_regime(train_data)[0],
                "returns": test_perf["total_return"],
                "vol": test_perf["realized_vol"],
                "sharpe": test_perf["sharpe"],
                "max_drawdown": test_perf["max_drawdown"],
                "n_assets": len(weights_df),
                "top_assets": cast(Any, weights_df.head(5)).to_dict(orient="records"),
            }
            results.append(window_res)
            cumulative_returns = pd.concat([cumulative_returns, test_perf["daily_returns"]])

        summary = self._summarize_results(results, cumulative_returns)
        return {"summary": summary, "windows": results}

    def run_tournament(
        self,
        *,
        train_window: int = 120,
        test_window: int = 20,
        step_size: int = 20,
        profiles: Optional[List[str]] = None,
        engines: Optional[List[str]] = None,
        cluster_cap: float = 0.25,
        simulators: Optional[List[str]] = None,
    ) -> Dict:
        settings = get_settings()
        profiles = [p.strip().lower() for p in (profiles or ["min_variance", "hrp", "max_sharpe", "barbell"]) if (p or "").strip()]
        engines = [e.strip().lower() for e in (engines or ["custom", "skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio", "market"]) if (e or "").strip()]
        sim_names = [s.strip().lower() for s in (simulators or ["custom", "cvxportfolio", "vectorbt"]) if (s or "").strip()]

        available_engines = set(list_available_engines())
        results: Dict[str, Dict[str, Any]] = {s: {} for s in sim_names}
        cumulative: Dict[tuple[str, str, str], pd.Series] = {}
        prev_weights: Dict[tuple[str, str, str], pd.Series] = {}

        # Warm-Start Initialization
        initial_holdings = self._load_initial_state()

        # Setup Audit Ledger if enabled
        run_dir = settings.prepare_summaries_run_dir()
        ledger = None
        if settings.features.feat_audit_ledger:
            ledger = AuditLedger(run_dir)

        for s in sim_names:
            for eng in engines:
                results[s][eng] = {}
                if eng not in available_engines:
                    results[s][eng]["_status"] = {"skipped": True, "reason": "engine unavailable"}
                    continue
                for prof in profiles if eng != "market" else ["min_variance"]:
                    results[s][eng][prof] = {"windows": [], "summary": None}
                    cumulative[(s, eng, prof)] = pd.Series(dtype=float)
                    # Initialize with warm-start holdings if available
                    prev_weights[(s, eng, prof)] = initial_holdings.get(prof, pd.Series(dtype=float))

        total_len = len(self.returns)
        if total_len < train_window + test_window:
            return {"meta": {"error": "data too short"}, "results": results}

        from scripts.natural_selection import run_selection

        for start_idx in range(0, total_len - train_window - test_window + 1, step_size):
            train_end = start_idx + train_window
            train_data_raw = self.returns.iloc[start_idx:train_end]
            test_data = self.returns.iloc[train_end : train_end + test_window]
            regime = self.detector.detect_regime(train_data_raw)[0]

            stats_df = self._audit_training_stats(train_data_raw)

            if settings.dynamic_universe and self.raw_candidates:
                winners = run_selection(train_data_raw, self.raw_candidates, stats_df=stats_df, top_n=settings.top_n, threshold=settings.threshold, m_gate=settings.min_momentum_score)
                current_symbols = [w["symbol"] for w in winners if w["symbol"] in train_data_raw.columns]
                if settings.baseline_symbol in train_data_raw.columns and settings.baseline_symbol not in current_symbols:
                    current_symbols.append(settings.baseline_symbol)
                train_data, candidate_meta = train_data_raw[current_symbols], {w["symbol"]: w for w in winners}
            else:
                train_data, candidate_meta = train_data_raw, {}

            clusters = self._cluster_data(train_data)
            # Re-audit for the filtered symbols
            stats_df_final = self._audit_training_stats(train_data)

            cached_weights = {}
            for eng in engines:
                if eng not in available_engines:
                    continue
                for prof in profiles if eng != "market" else ["min_variance"]:
                    try:
                        p_weights = prev_weights.get(("cvxportfolio" if "cvxportfolio" in sim_names else sim_names[0], eng, prof))

                        if ledger:
                            ledger.record_intent(
                                step="backtest_optimize",
                                params={"engine": eng, "profile": prof, "start": str(train_data.index[0]), "end": str(train_data.index[-1])},
                                input_hashes={"train_returns": get_df_hash(train_data)},
                            )

                        weights_df = self._compute_weights(train_data, clusters, stats_df_final, prof, eng, cluster_cap, candidate_meta, cast(pd.Series, p_weights), regime)

                        if ledger and not weights_df.empty:
                            ledger.record_outcome(step="backtest_optimize", status="success", output_hashes={"window_weights": get_df_hash(weights_df)}, metrics={"n_assets": len(weights_df)})

                        if not weights_df.empty:
                            cached_weights[(eng, prof)] = weights_df
                    except Exception as e:
                        for s in sim_names:
                            results[s][eng][prof].setdefault("errors", []).append(str(e))

            for s_name in sim_names:
                simulator = build_simulator(s_name)
                for (eng, prof), weights_df in cached_weights.items():
                    if (s_name, eng, prof) not in cumulative:
                        continue
                    try:
                        p_holdings = prev_weights.get((s_name, eng, prof))
                        perf = simulator.simulate(test_data, weights_df, initial_holdings=p_holdings)

                        # Capture realized ending state for next window transition
                        if "final_weights" in perf:
                            prev_weights[(s_name, eng, prof)] = perf["final_weights"]
                        else:
                            # Fallback: target weights become starting holdings
                            w_series = weights_df.set_index("Symbol")["Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"].astype(float).fillna(0.0)
                            prev_weights[(s_name, eng, prof)] = w_series

                        results[s_name][eng][prof]["windows"].append(
                            {
                                "engine": eng,
                                "profile": prof,
                                "simulator": s_name,
                                "start_date": str(test_data.index[0]),
                                "end_date": str(test_data.index[-1]),
                                "regime": regime,
                                "returns": perf["total_return"],
                                "vol": perf["realized_vol"],
                                "sharpe": perf["sharpe"],
                                "max_drawdown": perf["max_drawdown"],
                                "turnover": perf.get("turnover", 0.0),
                                "n_assets": len(weights_df),
                                "top_assets": cast(Any, weights_df.head(5)).to_dict(orient="records"),
                            }
                        )
                        cumulative[(s_name, eng, prof)] = pd.concat([cumulative[(s_name, eng, prof)], perf["daily_returns"]])
                    except Exception as e:
                        results[s_name][eng][prof].setdefault("errors", []).append(str(e))

        for s_name in sim_names:
            for eng, prof_map in results[s_name].items():
                if prof_map.get("_status"):
                    continue
                for prof, p_data in prof_map.items():
                    if prof == "_status" or not p_data.get("windows"):
                        continue
                    p_data["summary"] = self._summarize_results(p_data["windows"], cumulative[(s_name, eng, prof)])
        return {
            "meta": {"train_window": train_window, "test_window": test_window, "simulators": sim_names},
            "results": results,
            "returns": {f"{s}_{e}_{p}": v for (s, e, p), v in cumulative.items() if not v.empty},
        }

    def _cluster_data(self, df: pd.DataFrame, threshold: Optional[float] = None) -> Dict[str, List[str]]:
        import scipy.cluster.hierarchy as sch
        from scipy.spatial.distance import squareform
        import importlib

        settings = get_settings()
        t = threshold if threshold is not None else settings.threshold

        get_robust_correlation = importlib.import_module("scripts.natural_selection").get_robust_correlation
        corr = get_robust_correlation(df)
        dist = np.sqrt(0.5 * (1 - corr.values.clip(-1, 1)))
        dist = (dist + dist.T) / 2
        np.fill_diagonal(dist, 0)
        link = sch.linkage(squareform(dist, checks=False), method="ward")

        if settings.features.feat_pit_fidelity:
            cluster_ids = sch.fcluster(link, t=t, criterion="distance")
        else:
            cluster_ids = sch.fcluster(link, t=10, criterion="maxclust")

        clusters = {}
        for sym, c_id in zip(df.columns, cluster_ids):
            cid = str(c_id)
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(str(sym))
        return clusters

    def _audit_training_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        settings = get_settings()
        if settings.features.feat_pit_fidelity:
            auditor = AntifragilityAuditor()
            return auditor.audit(df)

        return pd.DataFrame([{"Symbol": s, "Vol": df[s].std() * np.sqrt(252), "Return": df[s].mean() * 252, "Antifragility_Score": 0.5} for s in df.columns])

    def _compute_weights(
        self,
        train_data: pd.DataFrame,
        clusters: Dict[str, List[str]],
        stats_df: pd.DataFrame,
        profile: str,
        engine: str,
        cluster_cap: float,
        meta: Dict[str, Any],
        prev_weights: Optional[pd.Series] = None,
        regime: str = "NORMAL",
    ) -> pd.DataFrame:
        request = EngineRequest(profile=cast(ProfileName, profile), cluster_cap=cluster_cap, prev_weights=prev_weights, regime=regime)
        resp = build_engine(engine).optimize(returns=train_data, clusters=clusters, meta=meta, stats=stats_df, request=request)
        return resp.weights

    def _summarize_results(self, windows: List[Dict], cumulative_returns: pd.Series) -> Dict:
        from tradingview_scraper.utils.metrics import calculate_performance_metrics

        summary = calculate_performance_metrics(cumulative_returns)
        summary.update(
            {
                "total_cumulative_return": summary["total_return"],
                "avg_window_return": float(np.mean([w["returns"] for w in windows])),
                "avg_window_sharpe": float(np.mean([w["sharpe"] for w in windows])),
                "avg_turnover": float(np.mean([w.get("turnover", 0.0) for w in windows])),
                "win_rate": float(np.mean([1 if w["returns"] > 0 else 0 for w in windows])),
            }
        )
        return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=120)
    parser.add_argument("--test", type=int, default=20)
    parser.add_argument("--step", type=int, default=20)
    parser.add_argument("--cluster-cap", type=float, default=0.25)
    parser.add_argument("--simulators")
    parser.add_argument("--engines")
    parser.add_argument("--profiles")
    parser.add_argument("--tournament", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    bt = BacktestEngine()

    if args.tournament:
        full_results = bt.run_tournament(
            train_window=args.train,
            test_window=args.test,
            step_size=args.step,
            profiles=cast(List[str], (args.profiles or "").split(",")),
            engines=cast(List[str], (args.engines or "").split(",")),
            cluster_cap=args.cluster_cap,
            simulators=cast(List[str], (args.simulators or "").split(",")),
        )
        output_dir = settings.prepare_summaries_run_dir()
        with open(output_dir / "tournament_results.json", "w") as f:
            json.dump({"meta": full_results["meta"], "results": full_results["results"]}, f, indent=2)
        if "returns" in full_results:
            returns_dir = output_dir / "returns"
            returns_dir.mkdir(exist_ok=True)
            for key, series in full_results["returns"].items():
                series.to_pickle(returns_dir / f"{key}.pkl")
