import argparse
import hashlib
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingview_scraper.portfolio_engines.backtest_simulators import build_simulator
from tradingview_scraper.portfolio_engines.base import EngineRequest, ProfileName
from tradingview_scraper.portfolio_engines.engines import build_engine, list_available_engines
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.risk import AntifragilityAuditor
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backtest_engine")


class BacktestEngine:
    def __init__(self, returns_path: str = "data/lakehouse/portfolio_returns.pkl"):
        env_override = os.getenv("BACKTEST_RETURNS_PATH") or os.getenv("TV_RETURNS_PATH")
        if env_override and returns_path == "data/lakehouse/portfolio_returns.pkl":
            returns_path = env_override
        if not os.path.exists(returns_path):
            raise FileNotFoundError(f"Returns matrix missing: {returns_path}")

        with open(returns_path, "rb") as f_in:
            df = cast(pd.DataFrame, pd.read_pickle(f_in))
            try:
                new_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in df.index]
                df.index = pd.DatetimeIndex(new_idx)
            except Exception as e_idx:
                logger.warning(f"Fallback indexing for returns: {e_idx}")
                df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
            self.returns = df

        self.raw_returns = None
        raw_returns_path = os.getenv("RAW_POOL_RETURNS_PATH") or os.getenv("TV_RAW_POOL_RETURNS_PATH") or "data/lakehouse/portfolio_returns_raw.pkl"
        if os.path.exists(raw_returns_path):
            with open(raw_returns_path, "rb") as f_in:
                df_raw = cast(pd.DataFrame, pd.read_pickle(f_in))
                try:
                    new_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in df_raw.index]
                    df_raw.index = pd.DatetimeIndex(new_idx)
                except Exception as e_idx:
                    logger.warning(f"Fallback indexing for raw returns: {e_idx}")
                    df_raw.index = pd.to_datetime(df_raw.index, utc=True).tz_convert(None)
                self.raw_returns = df_raw

        self.raw_candidates = []
        raw_path = "data/lakehouse/portfolio_candidates_raw.json"
        if os.path.exists(raw_path):
            with open(raw_path, "r") as f:
                self.raw_candidates = json.load(f)

        self.detector = MarketRegimeDetector()

    def _load_initial_state(self) -> Dict[str, pd.Series]:
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
                initial_holdings[profile] = pd.Series({a["Symbol"]: float(a.get("Weight", 0.0)) for a in assets})
            return initial_holdings
        except Exception as e:
            logger.warning(f"Failed to load initial state: {e}")
            return {}

    def run_tournament(
        self,
        *,
        train_window: Optional[int] = None,
        test_window: Optional[int] = None,
        step_size: Optional[int] = None,
        profiles: Optional[List[str]] = None,
        engines: Optional[List[str]] = None,
        cluster_cap: float = 0.25,
        simulators: Optional[List[str]] = None,
        bayesian_params: Optional[Dict[str, Any]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        settings = get_settings()
        if train_window is None:
            train_window = int(settings.train_window)
        if test_window is None:
            test_window = int(settings.test_window)
        if step_size is None:
            step_size = int(settings.step_size)
        b_params = bayesian_params or {}
        profiles = [p.strip().lower() for p in (profiles or ["min_variance", "hrp", "max_sharpe", "barbell"]) if (p or "").strip()]
        engines = [e.strip().lower() for e in (engines or ["custom", "skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio"]) if (e or "").strip()]
        sim_names = [s.strip().lower() for s in (simulators or ["custom", "cvxportfolio", "vectorbt", "nautilus"]) if (s or "").strip()]
        if not profiles:
            profiles = ["min_variance", "hrp", "max_sharpe", "barbell"]
        if not engines:
            engines = ["custom", "skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio"]
        if not sim_names:
            sim_names = ["custom", "cvxportfolio", "vectorbt", "nautilus"]

        raw_pool_universe = (settings.raw_pool_universe or "selected").strip().lower()
        if raw_pool_universe not in {"selected", "canonical"}:
            logger.warning("Unknown raw_pool_universe '%s'; falling back to 'selected'.", raw_pool_universe)
            raw_pool_universe = "selected"

        returns_to_use = cast(pd.DataFrame, self.returns)
        if start_date:
            returns_to_use = cast(pd.DataFrame, returns_to_use[returns_to_use.index >= pd.to_datetime(start_date)])
        if end_date:
            returns_to_use = cast(pd.DataFrame, returns_to_use[returns_to_use.index <= pd.to_datetime(end_date)])

        returns_to_use = returns_to_use.dropna(how="all")

        raw_returns_to_use = None
        if raw_pool_universe == "canonical":
            if self.raw_returns is None:
                logger.warning("raw_pool_universe set to canonical but raw returns matrix is missing; falling back to selected.")
                raw_pool_universe = "selected"
            else:
                raw_returns_to_use = self.raw_returns
                if start_date:
                    raw_returns_to_use = cast(pd.DataFrame, raw_returns_to_use[raw_returns_to_use.index >= pd.to_datetime(start_date)])
                if end_date:
                    raw_returns_to_use = cast(pd.DataFrame, raw_returns_to_use[raw_returns_to_use.index <= pd.to_datetime(end_date)])
                # Align canonical returns to the primary index so windows stay consistent
                raw_returns_to_use = cast(pd.DataFrame, raw_returns_to_use.reindex(returns_to_use.index))

        available_engines = set(list_available_engines())
        results: Dict[str, Dict[str, Any]] = {s: {} for s in sim_names}
        cumulative: Dict[tuple[str, str, str], List[pd.Series]] = {}
        prev_weights: Dict[tuple[str, str, str], pd.Series] = {}

        initial_holdings = self._load_initial_state()
        run_dir = settings.prepare_summaries_run_dir()
        ledger = AuditLedger(run_dir) if settings.features.feat_audit_ledger else None

        baseline_engine = "market"
        baseline_profiles = ["market", "equal_weight", "raw_pool_ew"]

        context_base = {
            "selection_mode": settings.features.selection_mode,
            "rebalance_mode": settings.features.feat_rebalance_mode,
            "train_window": train_window,
            "test_window": test_window,
            "step_size": step_size,
            "start_date": start_date,
            "end_date": end_date,
        }

        for s in sim_names:
            for eng in engines:
                results[s][eng] = {}
                if eng not in available_engines:
                    results[s][eng]["_status"] = {"skipped": True, "reason": "engine unavailable"}
                    continue
                for prof in profiles:
                    results[s][eng][prof] = {"windows": [], "summary": None}
                    cumulative[(s, eng, prof)] = []
                    prev_weights[(s, eng, prof)] = initial_holdings.get(prof, pd.Series(dtype=float))

                if eng == "custom" and settings.dynamic_universe:
                    for prof in ["market_baseline", "benchmark_baseline"]:
                        results[s][eng][prof] = {"windows": [], "summary": None}
                        cumulative[(s, eng, prof)] = []
                        prev_weights[(s, eng, prof)] = pd.Series(dtype=float)

            results[s][baseline_engine] = {}
            for prof in baseline_profiles:
                results[s][baseline_engine][prof] = {"windows": [], "summary": None}
                cumulative[(s, baseline_engine, prof)] = []
                prev_weights[(s, baseline_engine, prof)] = pd.Series(dtype=float)

        total_len = len(returns_to_use)
        if total_len < train_window + test_window:
            return {"meta": {"error": "data too short"}, "results": results}

        from scripts.natural_selection import run_selection

        for window_index, start_idx in enumerate(range(0, total_len - train_window - test_window + 1, step_size)):
            train_end = start_idx + train_window
            train_data_raw = returns_to_use.iloc[start_idx:train_end]

            # EXTENDED TEST DATA: include one extra day for simulator alignment
            test_end_idx = min(train_end + test_window + 1, total_len)
            test_data_extended = returns_to_use.iloc[train_end:test_end_idx]
            # Standard test data for metadata and non-extended simulators
            test_data = returns_to_use.iloc[train_end : train_end + test_window]

            raw_train_data_raw = None
            raw_test_data_extended = None
            raw_test_data = None
            raw_window_slice = None
            if raw_returns_to_use is not None:
                raw_train_data_raw = raw_returns_to_use.iloc[start_idx:train_end]
                raw_test_data_extended = raw_returns_to_use.iloc[train_end:test_end_idx]
                raw_test_data = raw_returns_to_use.iloc[train_end : train_end + test_window]
                raw_window_slice = raw_returns_to_use.iloc[start_idx:test_end_idx]

            window_slice = returns_to_use.iloc[start_idx:test_end_idx]
            valid_symbols = [c for c in window_slice.columns if window_slice[c].notna().all()]
            if not valid_symbols:
                logger.warning("Window %s has no symbols with full data; skipping.", window_index)
                continue

            train_data_raw = train_data_raw[valid_symbols]
            test_data = test_data[valid_symbols]
            test_data_extended = test_data_extended[valid_symbols]

            raw_pool_candidates = list(train_data_raw.columns)
            raw_pool_universe_resolved = "selected"
            if raw_pool_universe == "canonical":
                canonical_symbols = []
                for c in self.raw_candidates:
                    if isinstance(c, dict):
                        canonical_symbols.append(c.get("symbol"))
                    else:
                        canonical_symbols.append(str(c))
                canonical_symbols = [s for s in canonical_symbols if s]
                if canonical_symbols:
                    raw_pool_candidates = canonical_symbols
                    raw_pool_universe_resolved = "canonical"
                else:
                    logger.warning("raw_pool_universe set to canonical but raw candidates are empty; using selected universe.")

            raw_pool_train_data = train_data_raw
            raw_pool_test_data = test_data
            raw_pool_test_data_extended = test_data_extended
            raw_pool_window_slice = window_slice
            if raw_pool_universe_resolved == "canonical" and raw_train_data_raw is not None:
                raw_pool_train_data = raw_train_data_raw
                raw_pool_test_data = raw_test_data if raw_test_data is not None else test_data
                raw_pool_test_data_extended = raw_test_data_extended if raw_test_data_extended is not None else test_data_extended
                raw_pool_window_slice = raw_window_slice if raw_window_slice is not None else window_slice

            if raw_pool_universe_resolved == "canonical":
                if not any(s in raw_pool_train_data.columns for s in raw_pool_candidates):
                    logger.warning("canonical raw_pool_universe has no overlap with returns matrix; falling back to selected.")
                    raw_pool_candidates = list(train_data_raw.columns)
                    raw_pool_universe_resolved = "selected"
                    raw_pool_train_data = train_data_raw
                    raw_pool_test_data = test_data
                    raw_pool_test_data_extended = test_data_extended
                    raw_pool_window_slice = window_slice

            window_context_base = {
                **context_base,
                "window_index": window_index,
                "train_start": str(train_data_raw.index[0]),
                "test_start": str(test_data.index[0]),
                "test_end": str(test_data.index[-1]),
                "universe_source": raw_pool_universe_resolved,
            }

            regime = self.detector.detect_regime(train_data_raw)[0]
            market_env, _ = cast(Any, self.detector).detect_quadrant_regime(train_data_raw)
            stats_df = self._audit_training_stats(train_data_raw)

            if settings.dynamic_universe and self.raw_candidates:
                response = run_selection(
                    train_data_raw,
                    self.raw_candidates,
                    stats_df=stats_df,
                    top_n=settings.top_n,
                    threshold=settings.threshold,
                    m_gate=settings.min_momentum_score,
                )
                winners = getattr(response, "winners", None)
                if winners is None and isinstance(response, tuple):
                    winners = response[0]
                winners = winners or []
                current_symbols = [w["symbol"] for w in winners if w["symbol"] in train_data_raw.columns]
                for b_sym in settings.benchmark_symbols:
                    if b_sym in train_data_raw.columns and b_sym not in current_symbols:
                        current_symbols.append(b_sym)
                train_data, candidate_meta = train_data_raw[current_symbols], {w["symbol"]: w for w in winners}
            else:
                train_data, candidate_meta = train_data_raw, {}

            clusters = self._cluster_data(train_data)
            stats_df_final = self._audit_training_stats(train_data)
            cached_weights = {}

            for eng in engines:
                if eng not in available_engines:
                    continue
                for prof in results[sim_names[0]][eng].keys():
                    if prof in ["_status", "market_baseline", "benchmark_baseline"]:
                        continue
                    try:
                        p_weights = prev_weights.get((sim_names[0], eng, prof))
                        if ledger:
                            c_hash = hashlib.sha256(json.dumps(clusters, sort_keys=True).encode()).hexdigest()
                            opt_context = {
                                **window_context_base,
                                "engine": eng,
                                "profile": prof,
                            }
                            ledger.record_intent(
                                step="backtest_optimize",
                                params={"engine": eng, "profile": prof, "regime": regime},
                                input_hashes={"train_returns": get_df_hash(train_data), "clusters": c_hash},
                                context=opt_context,
                            )
                        weights_df = self._compute_weights(
                            train_data,
                            clusters,
                            stats_df_final,
                            prof,
                            eng,
                            cluster_cap,
                            candidate_meta,
                            cast(pd.Series, p_weights),
                            regime,
                            market_env,
                            bayesian_params=b_params,
                        )
                        if ledger and not weights_df.empty:
                            opt_context = {
                                **window_context_base,
                                "engine": eng,
                                "profile": prof,
                            }
                            ledger.record_outcome(
                                step="backtest_optimize",
                                status="success",
                                output_hashes={"window_weights": get_df_hash(weights_df)},
                                metrics={"n_assets": len(weights_df)},
                                data={"weights": weights_df.set_index("Symbol")["Weight"].to_dict()},
                                context=opt_context,
                            )
                        if not weights_df.empty:
                            cached_weights[(eng, prof)] = weights_df
                    except Exception as e:
                        logger.error(f"Engine {eng} Profile {prof} failed: {e}")

            # Special Baselines
            try:
                raw_w_df = None
                raw_pool_symbol_count = 0
                raw_pool_returns_hash = None
                w_market = self._compute_weights(train_data_raw, clusters, stats_df_final, "market", "custom", 1.0, candidate_meta, None, regime, market_env)
                if not w_market.empty:
                    cached_weights[(baseline_engine, "market")] = w_market
                w_filt = self._compute_weights(train_data, clusters, stats_df_final, "equal_weight", "custom", cluster_cap, candidate_meta, None, regime, market_env)
                if not w_filt.empty:
                    cached_weights[(baseline_engine, "equal_weight")] = w_filt

                # Raw Pool Equal Weight (Selection Alpha Baseline)
                valid_raw_symbols = []
                if raw_pool_window_slice is not None:
                    valid_raw_symbols = [s for s in raw_pool_candidates if s in raw_pool_window_slice.columns and raw_pool_window_slice[s].notna().all() and s not in settings.benchmark_symbols]
                else:
                    valid_raw_symbols = [s for s in raw_pool_candidates if s in train_data_raw.columns and s not in settings.benchmark_symbols]
                if valid_raw_symbols:
                    raw_w_df = pd.DataFrame([{"Symbol": s, "Weight": 1.0 / len(valid_raw_symbols)} for s in valid_raw_symbols])
                    cached_weights[(baseline_engine, "raw_pool_ew")] = raw_w_df
                    raw_pool_symbol_count = len(valid_raw_symbols)
                    if ledger:
                        raw_pool_returns_hash = get_df_hash(raw_pool_train_data[valid_raw_symbols])

                # Backwards-compatible baselines under custom engine (dynamic universe)
                if settings.dynamic_universe and "custom" in engines:
                    if not w_market.empty:
                        cached_weights[("custom", "market_baseline")] = w_market
                    w_bench = self._compute_weights(train_data_raw, clusters, stats_df_final, "benchmark", "custom", 1.0, candidate_meta, None, regime, market_env)
                    if not w_bench.empty:
                        cached_weights[("custom", "benchmark_baseline")] = w_bench
                    if raw_w_df is not None:
                        cached_weights[("custom", "raw_pool_ew")] = raw_w_df

            except Exception as e:
                logger.error(f"Failed baselines: {e}")

            for s_name in sim_names:
                simulator = build_simulator(s_name)
                for (eng, prof), w_df in cached_weights.items():
                    if (s_name, eng, prof) not in cumulative:
                        continue
                    try:
                        sim_test_extended = test_data_extended
                        if prof == "raw_pool_ew" and raw_pool_universe_resolved == "canonical":
                            sim_test_extended = raw_pool_test_data_extended
                        if sim_test_extended is None:
                            sim_test_extended = test_data_extended

                        # Use EXTENDED data for simulators that support it (CVXPortfolio)
                        perf = simulator.simulate(sim_test_extended, w_df, initial_holdings=prev_weights.get((s_name, eng, prof)))

                        # IMPORTANT: result['daily_returns'] must be capped back to test_window length
                        # to avoid window overlap in cumulative calculations
                        d_returns = perf["daily_returns"]
                        if len(d_returns) > test_window:
                            d_returns = d_returns.iloc[:test_window]

                        prev_weights[(s_name, eng, prof)] = perf.get("final_weights", w_df.set_index("Symbol")["Weight"].fillna(0.0))
                        # Calculate Condition Number (kappa) for Audit
                        kappa = 1.0
                        try:
                            # Use Train Data for kappa (input to optimizer)
                            corr = train_data.corr().fillna(0.0)
                            if not corr.empty:
                                eigenvalues = np.linalg.eigvalsh(corr.values)
                                kappa = float(eigenvalues.max() / (np.abs(eigenvalues).min() + 1e-15))
                        except Exception:
                            pass

                        results[s_name][eng][prof]["windows"].append(
                            {
                                "engine": eng,
                                "profile": prof,
                                "simulator": s_name,
                                "train_start": str(train_data.index[0]),
                                "start_date": str(test_data.index[0]),
                                "end_date": str(test_data.index[-1]),
                                "regime": regime,
                                "kappa": kappa,
                                "returns": perf["total_return"],
                                "vol": perf["realized_vol"],
                                "sharpe": perf["sharpe"],
                                "max_drawdown": perf["max_drawdown"],
                                "turnover": perf.get("turnover", 0.0),
                                "n_assets": len(w_df),
                                "top_assets": cast(Any, w_df.head(5)).to_dict(orient="records"),
                            }
                        )
                        if ledger:
                            sim_context = {
                                **window_context_base,
                                "engine": eng,
                                "profile": prof,
                                "simulator": s_name,
                            }
                            if prof == "raw_pool_ew":
                                if raw_pool_symbol_count:
                                    sim_context["raw_pool_symbol_count"] = raw_pool_symbol_count
                                if raw_pool_returns_hash:
                                    sim_context["raw_pool_returns_hash"] = raw_pool_returns_hash
                            ledger.record_outcome(
                                step="backtest_simulate",
                                status="success",
                                output_hashes={"test_returns": get_df_hash(d_returns)},
                                metrics={"eng": eng, "prof": prof, "sim": s_name, "sharpe": perf["sharpe"]},
                                context=sim_context,
                            )
                        cumulative[(s_name, eng, prof)].append(d_returns)
                    except Exception as e:
                        results[s_name][eng][prof].setdefault("errors", []).append(str(e))

        for s in sim_names:
            for eng, p_map in results[s].items():
                for prof, p_data in p_map.items():
                    if prof != "_status" and p_data.get("windows"):
                        full_rets = pd.concat(cumulative[(s, eng, prof)])
                        p_data["summary"] = self._summarize_results(p_data["windows"], full_rets)

        meta_plus = {"train_window": train_window, "test_window": test_window, "step_size": step_size, "simulators": sim_names}
        return {"meta": meta_plus, "results": results, "returns": {f"{s}_{e}_{p}": pd.concat(v) for (s, e, p), v in cumulative.items() if v}}

    def _cluster_data(self, df: pd.DataFrame, threshold: Optional[float] = None) -> Dict[str, List[str]]:
        from tradingview_scraper.selection_engines.engines import get_hierarchical_clusters

        settings = get_settings()
        t = threshold if threshold is not None else settings.threshold
        if df.shape[1] < 2:
            return {"0": [str(s) for s in df.columns]}
        try:
            ids, _ = get_hierarchical_clusters(df, threshold=t, max_clusters=10)
            clusters = {}
            for sym, cid in zip(df.columns, ids):
                c_str = str(cid)
                if c_str not in clusters:
                    clusters[c_str] = []
                clusters[c_str].append(str(sym))
            return clusters
        except Exception:
            return {"0": [str(s) for s in df.columns]}

    def _audit_training_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        if get_settings().features.feat_pit_fidelity:
            return AntifragilityAuditor().audit(df)
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
        market_env: str = "NORMAL",
        bayesian_params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        # Cast to Any to bypass linter issues with EngineRequest attributes
        req = cast(Any, EngineRequest)(
            profile=cast(ProfileName, profile),
            engine=engine,
            cluster_cap=cluster_cap,
            risk_free_rate=0.0,
            aggressor_weight=0.10,
            max_aggressor_clusters=5,
            regime=regime,
            market_environment=market_env,
            bayesian_params=bayesian_params or {},
            prev_weights=prev_weights,
        )
        return build_engine(engine).optimize(returns=train_data, clusters=clusters, meta=meta, stats=stats_df, request=req).weights

    def _summarize_results(self, windows: List[Dict], cumulative_returns: pd.Series) -> Dict:
        from tradingview_scraper.utils.metrics import calculate_performance_metrics

        s = calculate_performance_metrics(cumulative_returns)
        if not windows:
            s.update({"total_cumulative_return": s.get("total_return", 0.0), "avg_window_return": 0.0, "avg_window_sharpe": 0.0, "avg_turnover": 0.0, "win_rate": 0.0})
            return s
        s.update(
            {
                "total_cumulative_return": s["total_return"],
                "avg_window_return": float(np.mean([w["returns"] for w in windows])),
                "avg_window_sharpe": float(np.mean([w["sharpe"] for w in windows])),
                "avg_turnover": float(np.mean([w.get("turnover", 0.0) for w in windows])),
                "win_rate": float(np.mean([1 if w["returns"] > 0 else 0 for w in windows])),
            }
        )
        return s


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=None)
    parser.add_argument("--test", type=int, default=None)
    parser.add_argument("--step", type=int, default=None)
    parser.add_argument("--cluster-cap", type=float, default=None)
    parser.add_argument("--simulators")
    parser.add_argument("--engines")
    parser.add_argument("--profiles")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--tournament", action="store_true")
    args = parser.parse_args()
    bt = BacktestEngine()

    def _parse_list(arg: Optional[str]) -> Optional[List[str]]:
        if not arg:
            return None
        items = [s.strip() for s in arg.split(",") if s.strip()]
        return items or None

    if args.tournament:
        settings = get_settings()
        cluster_cap = float(args.cluster_cap) if args.cluster_cap is not None else float(settings.cluster_cap)
        res = bt.run_tournament(
            train_window=args.train,
            test_window=args.test,
            step_size=args.step,
            profiles=_parse_list(args.profiles),
            engines=_parse_list(args.engines),
            cluster_cap=cluster_cap,
            simulators=_parse_list(args.simulators),
            start_date=args.start_date,
            end_date=args.end_date,
        )
        settings = get_settings()
        out = settings.prepare_summaries_run_dir()
        data_dir = settings.run_data_dir
        with open(data_dir / "tournament_results.json", "w") as f:
            json.dump({"meta": res["meta"], "results": res["results"]}, f, indent=2)

        settings.promote_summaries_latest()

        if "returns" in res:
            ret_dir = data_dir / "returns"
            ret_dir.mkdir(parents=True, exist_ok=True)
            for k, v in res["returns"].items():
                v.to_pickle(ret_dir / f"{k}.pkl")
