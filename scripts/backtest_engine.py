import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, cast

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

try:
    import ray
except ImportError:
    ray = None

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backtest_engine")


def _ray_compute_weights(
    train_data: pd.DataFrame,
    clusters: Dict[str, List[str]],
    stats_df: pd.DataFrame,
    profile: str,
    engine: str,
    cluster_cap: float,
    meta: Dict[str, Any],
    prev_weights: Optional[pd.Series],
    regime: str,
    market_env: str,
    bayesian_params: Dict[str, Any],
) -> pd.DataFrame:
    """Standalone function for Ray execution."""
    from tradingview_scraper.portfolio_engines.base import EngineRequest, ProfileName
    from tradingview_scraper.portfolio_engines.engines import build_engine

    req = EngineRequest(
        profile=cast(ProfileName, profile),
        engine=engine,
        cluster_cap=cluster_cap,
        risk_free_rate=0.0,
        aggressor_weight=0.10,
        max_aggressor_clusters=5,
        regime=regime,
        market_environment=market_env,
        bayesian_params=bayesian_params,
        prev_weights=prev_weights,
    )
    return build_engine(engine).optimize(returns=train_data, clusters=clusters, meta=meta, stats=stats_df, request=req).weights


if ray:
    remote_compute_weights = ray.remote(_ray_compute_weights)
else:
    remote_compute_weights = None


class BacktestEngine:
    def _min_dynamic_universe_assets(self) -> int:
        try:
            return int(os.getenv("TV_MIN_DYNAMIC_UNIVERSE_ASSETS", "10"))
        except Exception:
            return 10

    def _max_symbol_daily_vol(self) -> float:
        try:
            return float(os.getenv("TV_MAX_SYMBOL_DAILY_VOL", "0.10"))
        except Exception:
            return 0.10

    def _max_symbol_abs_daily_return(self) -> float:
        try:
            return float(os.getenv("TV_MAX_SYMBOL_ABS_DAILY_RETURN", "0.20"))
        except Exception:
            return 0.20

    def _vol_filter_universe(self, returns: pd.DataFrame, *, context: str) -> List[str]:
        """Universal eligibility stabilizer."""
        if returns.empty or len(returns.columns) == 0:
            return [str(c) for c in returns.columns]

        max_daily_vol = self._max_symbol_daily_vol()
        max_abs_ret = self._max_symbol_abs_daily_return()
        try:
            vols = cast(pd.Series, returns.std(numeric_only=True)).dropna()
        except Exception:
            vols = cast(pd.Series, returns.apply(pd.to_numeric, errors="coerce").std()).dropna()

        if vols.empty:
            return [str(c) for c in returns.columns]

        try:
            max_abs = cast(pd.Series, returns.abs().max(numeric_only=True)).dropna()
        except Exception:
            max_abs = cast(pd.Series, returns.apply(pd.to_numeric, errors="coerce").abs().max()).dropna()

        eligible_mask = (vols <= max_daily_vol) & (max_abs <= max_abs_ret)
        eligible = [str(s) for s in vols[eligible_mask].index]

        if not eligible:
            return [str(c) for c in returns.columns]

        return eligible

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
            except Exception:
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
                except Exception:
                    df_raw.index = pd.to_datetime(df_raw.index, utc=True).tz_convert(None)
                self.raw_returns = df_raw

        self.raw_candidates = []
        raw_path = "data/lakehouse/portfolio_candidates_raw.json"
        if os.path.exists(raw_path):
            with open(raw_path, "r") as f:
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

    def _resolve_symbol_in_universe(self, symbol: str, *, universe_cols: List[str]) -> str:
        sym = str(symbol).strip()
        if not sym:
            return sym
        cols_set = set(universe_cols)
        if sym in cols_set:
            return sym
        exchange, ticker = sym.split(":", 1) if ":" in sym else (None, sym)
        ticker_map: Dict[str, List[str]] = {}
        for col in universe_cols:
            col_ticker = str(col).split(":", 1)[1] if ":" in str(col) else str(col)
            ticker_map.setdefault(col_ticker, []).append(str(col))
        matches = ticker_map.get(ticker) or []
        if not matches:
            return sym
        if exchange and f"{exchange}:{ticker}" in cols_set:
            return f"{exchange}:{ticker}"
        if len(matches) == 1:
            return matches[0]
        pref = ("NASDAQ:", "NYSE:", "AMEX:", "CME:", "CBOT:", "COMEX:", "NYMEX:", "FX:", "OANDA:", "BINANCE:", "COINBASE:", "KRAKEN:")
        for p in pref:
            for m in matches:
                if m.startswith(p):
                    return m
        return matches[0]

    def _resolve_symbols_in_universe(self, symbols: Iterable[str], *, universe_cols: Iterable[str]) -> List[str]:
        cols = [str(c) for c in universe_cols]
        resolved: List[str] = []
        seen = set()
        for s in symbols:
            r = self._resolve_symbol_in_universe(str(s), universe_cols=cols)
            if r and r not in seen:
                resolved.append(r)
                seen.add(r)
        return resolved

    def _ensure_ledger_genesis(self, ledger: AuditLedger, settings) -> None:
        if ledger.last_hash:
            return
        manifest_hash = hashlib.sha256(open(settings.manifest_path, "rb").read()).hexdigest() if settings.manifest_path.exists() else "unknown"
        ledger.record_genesis(settings.run_id, settings.profile, manifest_hash)

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
                if assets:
                    initial_holdings[profile] = pd.Series({a["Symbol"]: float(a.get("Weight", 0.0)) for a in assets})
            return initial_holdings
        except Exception:
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
        tw = train_window or int(settings.train_window)
        tew = test_window or int(settings.test_window)
        ss = step_size or int(settings.step_size)
        b_params = bayesian_params or {}
        profs = [p.strip().lower() for p in (profiles or settings.profiles.split(",")) if (p or "").strip()]
        engs = [e.strip().lower() for e in (engines or settings.engines.split(",")) if (e or "").strip()]
        if simulators is None:
            sim_names = [s.strip().lower() for s in settings.backtest_simulators.split(",") if s.strip()]
        else:
            sim_names = [s.strip().lower() for s in simulators if s.strip()]

        if settings.features.feat_rebalance_mode == "daily":
            ss = 1
        if not profs:
            profs = ["min_variance", "hrp", "max_sharpe", "barbell"]
        if not engs:
            engs = ["custom", "skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio"]
        if not sim_names:
            sim_names = ["custom", "cvxportfolio", "vectorbt"]

        raw_univ = (settings.raw_pool_universe or "selected").strip().lower()
        returns_to_use = cast(pd.DataFrame, self.returns)
        if start_date:
            returns_to_use = cast(pd.DataFrame, returns_to_use[returns_to_use.index >= pd.to_datetime(start_date)])
        if end_date:
            returns_to_use = cast(pd.DataFrame, returns_to_use[returns_to_use.index <= pd.to_datetime(end_date)])
        returns_to_use = returns_to_use.dropna(how="all")

        raw_returns_to_use = None
        if raw_univ == "canonical" and self.raw_returns is not None:
            raw_returns_to_use = self.raw_returns
            if start_date:
                raw_returns_to_use = cast(pd.DataFrame, raw_returns_to_use[raw_returns_to_use.index >= pd.to_datetime(start_date)])
            if end_date:
                raw_returns_to_use = cast(pd.DataFrame, raw_returns_to_use[raw_returns_to_use.index <= pd.to_datetime(end_date)])
            raw_returns_to_use = cast(pd.DataFrame, raw_returns_to_use.reindex(returns_to_use.index))

        available_engines = set(list_available_engines())
        results: Dict[str, Dict[str, Any]] = {s: {} for s in sim_names}
        cumulative: Dict[tuple[str, str, str], List[pd.Series]] = {}
        prev_weights: Dict[tuple[str, str, str], pd.Series] = {}

        initial_holdings = self._load_initial_state()
        run_dir = settings.prepare_summaries_run_dir()
        ledger = AuditLedger(run_dir) if settings.features.feat_audit_ledger else None
        if ledger:
            self._ensure_ledger_genesis(ledger, settings)

        baseline_engine = "market"
        baseline_profiles = ["market", "benchmark", "raw_pool_ew"]
        context_base = {
            "selection_mode": settings.features.selection_mode,
            "rebalance_mode": settings.features.feat_rebalance_mode,
            "train_window": tw,
            "test_window": tew,
            "step_size": ss,
            "start_date": start_date,
            "end_date": end_date,
            "run_id": settings.run_id,
            "profile_manifest": settings.profile,
        }

        for s in sim_names:
            for eng in engs:
                results[s][eng] = {}
                if eng not in available_engines:
                    results[s][eng]["_status"] = {"skipped": True, "reason": "engine unavailable"}
                    continue
                for prof in profs:
                    results[s][eng][prof] = {"windows": [], "summary": None}
                    cumulative[(s, eng, prof)] = []
                    prev_weights[(s, eng, prof)] = initial_holdings.get(prof, pd.Series(dtype=float))
            results[s][baseline_engine] = {}
            for prof in baseline_profiles:
                results[s][baseline_engine][prof] = {"windows": [], "summary": None}
                cumulative[(s, baseline_engine, prof)] = []
                prev_weights[(s, baseline_engine, prof)] = pd.Series(dtype=float)

        total_len = len(returns_to_use)
        if total_len < tw + tew:
            return {"meta": {"error": "data too short"}, "results": results}

        from scripts.natural_selection import run_selection

        window_index = 0
        for window_index, start_idx in enumerate(range(0, total_len - tw - tew + 1, ss)):
            train_end = start_idx + tw
            train_data_raw = returns_to_use.iloc[start_idx:train_end]
            test_end_idx = min(train_end + tew + 1, total_len)
            test_data_extended = returns_to_use.iloc[train_end:test_end_idx]
            test_data = returns_to_use.iloc[train_end : train_end + tew]

            raw_train_data_raw = raw_returns_to_use.iloc[start_idx:train_end] if raw_returns_to_use is not None else None
            raw_test_data_extended = raw_returns_to_use.iloc[train_end:test_end_idx] if raw_returns_to_use is not None else None
            raw_pool_window_slice = raw_returns_to_use.iloc[start_idx:test_end_idx] if raw_returns_to_use is not None else None

            valid_symbols = [c for c in returns_to_use.iloc[start_idx:test_end_idx].columns if returns_to_use.iloc[start_idx:test_end_idx][c].notna().all()]
            if not valid_symbols:
                continue
            train_data_raw, test_data, test_data_extended = train_data_raw[valid_symbols], test_data[valid_symbols], test_data_extended[valid_symbols]

            raw_pool_candidates = list(train_data_raw.columns)
            raw_univ_res = "selected"
            if raw_univ == "canonical":
                canon = [str(c.get("symbol") if isinstance(c, dict) else c) for c in self.raw_candidates if c]
                if canon:
                    raw_pool_candidates = self._resolve_symbols_in_universe(cast(Iterable[str], canon), universe_cols=train_data_raw.columns)
                    raw_univ_res = "canonical"

            raw_pool_train_data = train_data_raw
            if raw_univ_res == "canonical" and raw_train_data_raw is not None:
                raw_pool_train_data = raw_train_data_raw

            window_context_base = {
                **context_base,
                "window_index": window_index,
                "train_start": str(train_data_raw.index[0]),
                "test_start": str(test_data.index[0]),
                "test_end": str(test_data.index[-1]),
                "universe_source": raw_univ_res,
            }

            decision_regime, decision_regime_score = self.detector.detect_regime(train_data_raw)
            decision_quadrant, _ = cast(Any, self.detector).detect_quadrant_regime(train_data_raw)
            regime = decision_regime
            market_env = decision_quadrant
            stats_df = self._audit_training_stats(train_data_raw)

            realized_regime, realized_regime_score, realized_quadrant = None, None, None
            if str(os.getenv("TV_ENABLE_REALIZED_REGIME", "")).lower() in {"1", "true", "yes"}:
                try:
                    realized_regime, realized_regime_score = self.detector.detect_regime(test_data)
                    realized_quadrant, _ = cast(Any, self.detector).detect_quadrant_regime(test_data)
                except Exception:
                    pass

            raw_candidates_norm = self._normalize_raw_candidates()
            eligible_cols = set(self._vol_filter_universe(train_data_raw, context=f"train_window:{window_index}"))

            if settings.dynamic_universe and self.raw_candidates:
                resolved_candidates = [
                    {**c, "symbol": self._resolve_symbol_in_universe(str(c.get("symbol", "")), universe_cols=[str(x) for x in train_data_raw.columns])} for c in raw_candidates_norm if c.get("symbol")
                ]
                try:
                    response = run_selection(train_data_raw, resolved_candidates, stats_df=stats_df, top_n=settings.top_n, threshold=settings.threshold, m_gate=settings.min_momentum_score)
                    winners = getattr(response, "winners", [])
                    winner_symbols = [w.get("symbol") for w in winners if w.get("symbol") in train_data_raw.columns]
                    current_symbols = [s for s in winner_symbols if s and str(s) not in set(str(b) for b in settings.benchmark_symbols)]
                    for b_sym in settings.benchmark_symbols:
                        if b_sym in train_data_raw.columns and b_sym not in current_symbols:
                            current_symbols.append(b_sym)
                    train_data, candidate_meta = train_data_raw[current_symbols], {str(w.get("symbol")): w for w in winners if w.get("symbol")}
                except Exception:
                    train_data, candidate_meta = train_data_raw, {}
            else:
                train_data, candidate_meta = train_data_raw, {}

            min_assets = self._min_dynamic_universe_assets()
            filtered_cols = [c for c in train_data.columns if str(c) in eligible_cols]
            if len(filtered_cols) >= min_assets:
                train_data = train_data.loc[:, filtered_cols]
            else:
                raw_filtered = [c for c in train_data_raw.columns if str(c) in eligible_cols]
                if len(raw_filtered) >= min_assets:
                    train_data, candidate_meta = train_data_raw.loc[:, raw_filtered], {}

            clusters = self._cluster_data(train_data)
            stats_df_final = self._audit_training_stats(train_data)
            cached_weights = {}

            # Parallel Optimization via Ray
            futures = {}
            use_ray = ray is not None and os.getenv("TV_USE_RAY", "1") == "1"
            if use_ray and ray:
                if not ray.is_initialized():
                    env_vars = {k: v for k, v in os.environ.items() if k.startswith("TV_")}
                    env_vars["PYTHONPATH"] = os.getenv("PYTHONPATH", "")
                    ray.init(ignore_reinit_error=True, runtime_env={"env_vars": env_vars, "working_dir": None})
                logger.info(f"Window {window_index}: Parallel optimization enabled (Ray)")

            for eng in engs:
                if eng not in available_engines:
                    continue
                for prof in results[sim_names[0]][eng].keys():
                    if prof in ["_status", "market_baseline", "benchmark_baseline"]:
                        continue
                    p_w = prev_weights[(sim_names[0], eng, prof)]
                    if use_ray and remote_compute_weights:
                        # Submit to Ray
                        futures[(eng, prof)] = remote_compute_weights.remote(train_data, clusters, stats_df_final, prof, eng, cluster_cap, candidate_meta, p_w, regime, market_env, b_params)
                    else:
                        try:
                            weights_df = self._compute_weights(train_data, clusters, stats_df_final, prof, eng, cluster_cap, candidate_meta, p_w, regime, market_env, b_params)
                            if not weights_df.empty:
                                cached_weights[(eng, prof)] = weights_df
                        except Exception as e:
                            logger.error(f"Engine {eng} Profile {prof} failed: {e}")

            if futures and ray:
                for (eng, prof), f in futures.items():
                    try:
                        res = ray.get(f)
                        if isinstance(res, pd.DataFrame):
                            cached_weights[(eng, prof)] = res
                    except Exception as e:
                        logger.error(f"Ray task failed for {eng}/{prof}: {e}")

            try:
                baseline_opt = build_engine("custom")
                w_market = baseline_opt.optimize(
                    returns=train_data_raw, clusters=clusters, meta=candidate_meta, stats=stats_df_final, request=EngineRequest(profile=cast(ProfileName, "market"), engine="custom", cluster_cap=1.0)
                ).weights
                if not w_market.empty:
                    cached_weights[(baseline_engine, "market")] = w_market
                w_bench = baseline_opt.optimize(
                    returns=train_data, clusters=clusters, meta=candidate_meta, stats=stats_df_final, request=EngineRequest(profile=cast(ProfileName, "benchmark"), engine="custom", cluster_cap=1.0)
                ).weights
                if not w_bench.empty:
                    cached_weights[(baseline_engine, "benchmark")] = w_bench
                valid_raw_symbols = [
                    s
                    for s in raw_pool_candidates
                    if s in (raw_pool_window_slice.columns if raw_pool_window_slice is not None else train_data_raw.columns)
                    and (raw_pool_window_slice[s].notna().all() if raw_pool_window_slice is not None else True)
                    and s not in settings.benchmark_symbols
                ]
                if valid_raw_symbols:
                    cached_weights[(baseline_engine, "raw_pool_ew")] = pd.DataFrame([{"Symbol": s, "Weight": 1.0 / len(valid_raw_symbols)} for s in valid_raw_symbols])
            except Exception as e:
                logger.error(f"Failed baselines: {e}")

            for s_name in sim_names:
                simulator = build_simulator(s_name)
                for (eng, prof), w_df in cached_weights.items():
                    if (s_name, eng, prof) not in prev_weights:
                        continue
                    try:
                        sim_test_extended = raw_test_data_extended if prof == "raw_pool_ew" and raw_univ_res == "canonical" and raw_test_data_extended is not None else test_data_extended
                        perf = simulator.simulate(sim_test_extended, w_df, initial_holdings=prev_weights[(s_name, eng, prof)])
                        prev_weights[(s_name, eng, prof)] = perf.get("final_weights", pd.Series(dtype=float))
                        results[s_name][eng][prof]["windows"].append(
                            {
                                "engine": eng,
                                "profile": prof,
                                "simulator": s_name,
                                "train_start": str(train_data.index[0]),
                                "start_date": str(test_data.index[0]),
                                "end_date": str(test_data.index[-1]),
                                "regime": regime,
                                "returns": perf["total_return"],
                                "vol": perf["realized_vol"],
                                "sharpe": perf["sharpe"],
                                "max_drawdown": perf["max_drawdown"],
                                "turnover": perf.get("turnover", 0.0),
                                "n_assets": len(w_df),
                            }
                        )
                        cumulative[(s_name, eng, prof)].append(cast(pd.Series, perf["daily_returns"].iloc[:tew]))
                    except Exception as e:
                        logger.error(f"Simulator {s_name} {eng}/{prof} failed: {e}")

        for s_name in sim_names:
            for eng in engs:
                if eng in results[s_name]:
                    for prof in results[s_name][eng].keys():
                        if prof != "_status" and cumulative.get((s_name, eng, prof)):
                            results[s_name][eng][prof]["summary"] = self._summarize_results(results[s_name][eng][prof]["windows"], pd.concat(cumulative[(s_name, eng, prof)]))
            for prof in baseline_profiles:
                if cumulative.get((s_name, baseline_engine, prof)):
                    results[s_name][baseline_engine][prof]["summary"] = self._summarize_results(
                        results[s_name][baseline_engine][prof]["windows"], pd.concat(cumulative[(s_name, baseline_engine, prof)])
                    )

        return {"results": results, "meta": {"completed_at": str(pd.Timestamp.now()), "n_windows": window_index + 1}}

    def _cluster_data(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        from tradingview_scraper.selection_engines.engines import get_hierarchical_clusters

        ids, _ = get_hierarchical_clusters(df, threshold=get_settings().threshold)
        clusters: Dict[str, List[str]] = {}
        for sym, c_id in zip(df.columns, ids):
            cid = str(int(c_id))
            clusters.setdefault(cid, []).append(str(sym))
        return clusters

    def _audit_training_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        if get_settings().features.feat_pit_fidelity:
            return AntifragilityAuditor().audit(df)
        return pd.DataFrame([{"Symbol": s, "Vol": df[s].std() * np.sqrt(252), "Return": df[s].mean() * 252, "Antifragility_Score": 0.5} for s in df.columns]).set_index("Symbol")

    def _compute_weights(self, train_data, clusters, stats_df, profile, engine, cluster_cap, meta, prev_weights, regime, market_env, b_params) -> pd.DataFrame:
        req = cast(Any, EngineRequest)(
            profile=cast(ProfileName, profile),
            engine=engine,
            cluster_cap=cluster_cap,
            risk_free_rate=0.0,
            aggressor_weight=0.10,
            max_aggressor_clusters=5,
            regime=regime,
            market_environment=market_env,
            bayesian_params=b_params,
            prev_weights=prev_weights,
        )
        return build_engine(engine).optimize(returns=train_data, clusters=clusters, meta=meta, stats=stats_df, request=req).weights

    def _summarize_results(self, windows: List[Dict], cumulative_returns: pd.Series) -> Dict:
        from tradingview_scraper.utils.metrics import calculate_performance_metrics

        rets = cumulative_returns[~cumulative_returns.index.duplicated(keep="last")] if cumulative_returns.index.has_duplicates else cumulative_returns
        return calculate_performance_metrics(rets, detailed=True)


def persist_tournament_artifacts(res: Dict[str, Any], data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with open(data_dir / "tournament_results.json", "w") as f:
        json.dump({"meta": res.get("meta", {}), "results": res.get("results", {})}, f, indent=2)


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
        ccap = float(args.cluster_cap) if args.cluster_cap is not None else float(settings.cluster_cap)
        res = bt.run_tournament(
            train_window=args.train,
            test_window=args.test,
            step_size=args.step,
            profiles=_parse_list(args.profiles),
            engines=_parse_list(args.engines),
            cluster_cap=ccap,
            simulators=_parse_list(args.simulators),
            start_date=args.start_date,
            end_date=args.end_date,
        )
        persist_tournament_artifacts(res, settings.prepare_summaries_run_dir() / "data")
