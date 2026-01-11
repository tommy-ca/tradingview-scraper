import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, cast

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingview_scraper.portfolio_engines.backtest_simulators import build_simulator
from tradingview_scraper.portfolio_engines.base import EngineRequest, ProfileName
from tradingview_scraper.portfolio_engines.engines import build_engine
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.risk import AntifragilityAuditor
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backtest_engine")


def persist_tournament_artifacts(results: Dict[str, Any], output_dir: Path):
    """Saves tournament metrics and windows to disk for analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "tournament_results.json", "w") as f:

        def _default(obj):
            if isinstance(obj, (pd.DataFrame, pd.Series)):
                return {}
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)

        json.dump(results, f, indent=2, default=_default)


class BacktestEngine:
    def __init__(self, returns_path: str = "data/lakehouse/portfolio_returns.pkl"):
        if not os.path.exists(returns_path):
            raise FileNotFoundError(f"Returns missing: {returns_path}")
        self.returns = cast(pd.DataFrame, pd.read_pickle(returns_path))
        self.raw_candidates = []
        raw_manifest = "data/lakehouse/portfolio_candidates_raw.json"
        if os.path.exists(raw_manifest):
            with open(raw_manifest, "r") as f:
                self.raw_candidates = json.load(f)
        settings = get_settings()
        self.detector = MarketRegimeDetector(audit_path=settings.summaries_run_dir / "regime_audit.jsonl")

    def _normalize_raw_candidates(self) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for c in self.raw_candidates:
            if isinstance(c, dict):
                sym = c.get("symbol")
                if sym:
                    normalized.append({**c, "symbol": str(sym)})
                continue
            sym = str(c).strip()
            if sym:
                normalized.append({"symbol": sym})
        return normalized

    def _resolve_symbol_in_universe(self, symbol: str, universe_cols: List[str]) -> str:
        sym = str(symbol).strip()
        if sym in set(universe_cols):
            return sym
        ticker = sym.split(":", 1)[1] if ":" in sym else sym
        matches = [col for col in universe_cols if str(col).endswith(f":{ticker}") or str(col) == ticker]
        return matches[0] if matches else sym

    def run_tournament(self, **kwargs) -> Dict:
        settings = get_settings()
        train_window = kwargs.get("train_window") or int(settings.train_window)
        test_window = kwargs.get("test_window") or int(settings.test_window)
        step_size = kwargs.get("step_size") or int(settings.step_size)
        profiles = kwargs.get("profiles") or [p.strip() for p in settings.profiles.split(",")]
        engines = kwargs.get("engines") or [e.strip() for e in settings.engines.split(",")]
        sim_names = kwargs.get("simulators") or [s.strip() for s in settings.backtest_simulators.split(",")]

        returns_to_use = self.returns.dropna(how="all")
        total_len = len(returns_to_use)
        baseline_engine = "market"
        baseline_profiles = ["market", "benchmark", "raw_pool_ew"]

        results: Dict[str, Dict[str, Any]] = {
            s: {e: {p: {"windows": [], "summary": None} for p in (profiles if e != baseline_engine else baseline_profiles)} for e in engines + [baseline_engine]} for s in sim_names
        }
        cumulative: Dict[tuple[str, str, str], List[pd.Series]] = {}
        prev_weights: Dict[tuple[str, str, str], pd.Series] = {}

        for s in sim_names:
            for eng in engines + [baseline_engine]:
                t_profs = profiles if eng != baseline_engine else baseline_profiles
                for prof in t_profs:
                    cumulative[(s, eng, prof)] = []
                    prev_weights[(s, eng, prof)] = pd.Series(dtype=float)

        from scripts.natural_selection import run_selection

        raw_candidates_norm = self._normalize_raw_candidates()

        for window_index, start_idx in enumerate(range(0, total_len - train_window - test_window + 1, step_size)):
            train_end = start_idx + train_window
            train_data_raw = returns_to_use.iloc[start_idx:train_end]
            test_data_extended = returns_to_use.iloc[train_end : min(train_end + test_window + 1, total_len)]

            regime, score, quadrant = self.detector.detect_regime(train_data_raw)
            stats_df = AntifragilityAuditor().audit(train_data_raw)

            # 1. Selection
            try:
                response = run_selection(train_data_raw, raw_candidates_norm, stats_df=stats_df, top_n=settings.top_n, threshold=settings.threshold)
                winners_list = response.winners or []
            except Exception:
                winners_list = []

            # Benchmark Isolation
            winner_symbols = [w.get("symbol") for w in winners_list if w.get("symbol") in train_data_raw.columns]
            current_symbols = [s for s in winner_symbols if s]
            if not current_symbols:
                train_data, candidate_meta = train_data_raw, {}
            else:
                train_data, candidate_meta = train_data_raw[current_symbols], {str(w.get("symbol")): w for w in winners_list if w.get("symbol")}

            clusters = self._cluster_data(train_data)
            cached_weights = {}
            for eng in engines:
                for prof in profiles:
                    try:
                        optimizer = build_engine(eng)
                        req = EngineRequest(
                            profile=cast(ProfileName, prof),
                            engine=eng,
                            cluster_cap=0.25,
                            prev_weights=prev_weights.get((sim_names[0], eng, prof)),
                            regime=regime,
                            market_environment=quadrant,
                        )
                        w_df = optimizer.optimize(returns=train_data, clusters=clusters, meta=candidate_meta, stats=stats_df, request=req).weights
                        if not w_df.empty:
                            cached_weights[(eng, prof)] = w_df
                    except Exception:
                        continue

            # 2. Baselines
            baseline_opt = build_engine("custom")
            for b_prof in ["market", "benchmark"]:
                w_b = baseline_opt.optimize(
                    returns=train_data_raw, clusters=clusters, meta=candidate_meta, stats=stats_df, request=EngineRequest(profile=cast(ProfileName, b_prof), engine="custom", cluster_cap=1.0)
                ).weights
                if not w_b.empty:
                    cached_weights[(baseline_engine, b_prof)] = w_b

            # 3. Simulation
            for s_name in sim_names:
                simulator = build_simulator(s_name)
                for (eng, prof), w_df in cached_weights.items():
                    if (s_name, eng, prof) not in cumulative:
                        continue
                    try:
                        perf = simulator.simulate(test_data_extended, w_df, initial_holdings=prev_weights.get((s_name, eng, prof)))
                        d_rets = perf["daily_returns"].iloc[:test_window]
                        prev_weights[(s_name, eng, prof)] = perf.get("final_weights", w_df.set_index("Symbol")["Weight"])
                        results[s_name][eng][prof]["windows"].append({"start_date": str(test_data_extended.index[0]), "sharpe": perf["sharpe"], "regime": regime})
                        cumulative[(s_name, eng, prof)].append(d_rets)
                    except Exception:
                        continue

        for s in sim_names:
            for eng, p_map in results[s].items():
                for prof, p_data in p_map.items():
                    if p_data.get("windows") and (s, eng, prof) in cumulative:
                        full_rets = pd.concat(cumulative[(s, eng, prof)])
                        ann_ret = float(full_rets.mean() * 252)
                        ann_vol = float(full_rets.std() * np.sqrt(252))
                        p_data["summary"] = {"annualized_return": ann_ret, "sharpe": ann_ret / ann_vol if ann_vol > 0 else 0}
        return {"results": results}

    def _cluster_data(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        from tradingview_scraper.selection_engines.engines import get_hierarchical_clusters

        if df.shape[1] < 2:
            return {"0": [str(s) for s in df.columns]}
        try:
            ids, _ = get_hierarchical_clusters(df, threshold=get_settings().threshold)
            clusters = {}
            for sym, cid in zip(df.columns, ids):
                clusters.setdefault(str(cid), []).append(str(sym))
            return clusters
        except Exception:
            return {"0": [str(s) for s in df.columns]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["production", "research"], default="research")
    parser.add_argument("--profile", default="crypto_production")
    parser.add_argument("--selection-modes", default="v3.2")
    parser.add_argument("--train-window", type=int, default=180)
    parser.add_argument("--test-window", type=int, default=40)
    parser.add_argument("--step-size", type=int, default=20)
    args = parser.parse_args()
    if args.mode == "research":
        os.environ["TV_PROFILE"] = args.profile
        os.environ["TV_FEATURES__SELECTION_MODE"] = args.selection_modes
        engine = BacktestEngine()
        engine.run_tournament(train_window=args.train_window, test_window=args.test_window, step_size=args.step_size)
        print(f"✅ Research Sweep Complete: {get_settings().run_id}")
