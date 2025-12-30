import importlib
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

from tradingview_scraper.portfolio_engines.backtest_simulators import build_simulator
from tradingview_scraper.portfolio_engines.base import EngineRequest, EngineUnavailableError
from tradingview_scraper.portfolio_engines.engines import build_engine, list_available_engines, list_known_engines
from tradingview_scraper.regime import MarketRegimeDetector
from tradingview_scraper.risk import AntifragilityAuditor, TailRiskAuditor
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backtest_engine")


class BacktestEngine:
    def __init__(
        self,
        returns_path: str = "data/lakehouse/portfolio_returns.pkl",
        meta_path: str = "data/lakehouse/portfolio_meta.json",
    ):
        if not os.path.exists(returns_path):
            raise FileNotFoundError(f"Returns file not found at {returns_path}")

        with open(returns_path, "rb") as f:
            self.returns = cast(pd.DataFrame, pd.read_pickle(f))

        with open(meta_path, "r") as f:
            self.meta = json.load(f)

        self.detector = MarketRegimeDetector()
        self.af_auditor = AntifragilityAuditor()
        self.tail_auditor = TailRiskAuditor()

    def _audit_training_stats(self, train_data: pd.DataFrame) -> pd.DataFrame:
        af_df = self.af_auditor.audit(train_data)
        tail_df = self.tail_auditor.calculate_metrics(train_data, confidence_level=0.95)

        stats_df = af_df
        if not tail_df.empty:
            stats_df = pd.merge(af_df, tail_df, on="Symbol", how="left")

        if stats_df.empty:
            return stats_df

        antif_max = float(stats_df["Antifragility_Score"].max()) if "Antifragility_Score" in stats_df.columns else 0.0
        anti_norm = stats_df["Antifragility_Score"] / (antif_max + 1e-9) if antif_max > 0 else pd.Series(0.0, index=stats_df.index)

        if "CVaR_95" in stats_df.columns:
            cvar_abs = np.abs(stats_df["CVaR_95"])
            cvar_norm = cvar_abs / (float(np.max(cvar_abs)) + 1e-9)
        else:
            cvar_norm = pd.Series(0.0, index=stats_df.index)

        stats_df["Fragility_Score"] = (1.0 - anti_norm) + cvar_norm
        return stats_df

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
        logger.info(f"Train: {train_window}d, Test: {test_window}d, Step: {step_size}d")

        simulator = build_simulator(simulator_name)

        total_len = len(self.returns)
        if total_len < train_window + test_window:
            logger.error(f"Insufficient data for backtest: {total_len} rows available.")
            return

        results = []
        cumulative_returns = pd.Series(dtype=float)

        # Start from enough history for first training window
        for start_idx in range(0, total_len - train_window - test_window + 1, step_size):
            train_end = start_idx + train_window
            test_end = train_end + test_window

            train_data = self.returns.iloc[start_idx:train_end]
            test_data = self.returns.iloc[train_end:test_end]

            # 1. Audit and Cluster on Training Data
            stats_df = self._audit_training_stats(train_data)
            clusters = self._cluster_data(train_data)

            # 2. Optimize on Training Data
            try:
                weights_df = self._compute_weights(train_data=train_data, clusters=clusters, stats_df=stats_df, profile=profile, engine=engine, cluster_cap=cluster_cap)
            except EngineUnavailableError as e:
                logger.error(str(e))
                return

            if weights_df.empty:
                logger.warning(f"No weights generated for window {start_idx}")
                continue

            # 3. Calculate Performance on Test Data
            test_perf = simulator.simulate(test_data, weights_df)

            top_cols = ["Symbol", "Weight"]
            for extra in ["Net_Weight", "Direction", "Cluster_ID"]:
                if extra in weights_df.columns:
                    top_cols.append(extra)

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
                "var_95": test_perf.get("var_95"),
                "cvar_95": test_perf.get("cvar_95"),
                "n_assets": len(weights_df),
                "top_assets": cast(Any, weights_df.head(5)[top_cols]).to_dict(orient="records"),
            }

            results.append(window_res)

            # Append to cumulative returns for tracking
            if cumulative_returns.empty:
                cumulative_returns = test_perf["daily_returns"]
            else:
                cumulative_returns = pd.concat([cumulative_returns, test_perf["daily_returns"]])

            logger.info(f"Window {window_res['start_date']} to {window_res['end_date']}: Ret={window_res['returns']:.2%}, Vol={window_res['vol']:.2%}, Sharpe={window_res['sharpe']:.2f}")

        # Summary Statistics
        if results:
            summary = self._summarize_results(results, cumulative_returns)
            return {"windows": results, "summary": summary}
        return None

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
        profiles = [p.strip().lower() for p in (profiles or ["min_variance", "hrp", "max_sharpe", "barbell"]) if (p or "").strip()]
        engines = [e.strip().lower() for e in (engines or ["custom", "skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio"]) if (e or "").strip()]
        sim_names = [s.strip().lower() for s in (simulators or ["custom"]) if (s or "").strip()]

        known_engines = set(list_known_engines())
        available_engines = set(list_available_engines())

        # Results structure: results[simulator][engine][profile]
        results: Dict[str, Dict[str, Any]] = {s: {} for s in sim_names}
        # Initialize engine status per simulator
        for s in sim_names:
            for eng in engines:
                results[s][eng] = {}
                if eng not in known_engines:
                    results[s][eng]["_status"] = {"skipped": True, "reason": "unknown engine"}
                    continue
                if eng not in available_engines:
                    results[s][eng]["_status"] = {"skipped": True, "reason": "engine not installed"}
                    continue
                for prof in profiles:
                    results[s][eng][prof] = {"windows": [], "summary": None}

        # Shared state for tracking cumulative returns and previous weights
        # Keys: (simulator, engine, profile)
        cumulative: Dict[tuple[str, str, str], pd.Series] = {}
        prev_weights: Dict[tuple[str, str, str], pd.Series] = {}
        for s in sim_names:
            for eng in engines:
                for prof in profiles:
                    cumulative[(s, eng, prof)] = pd.Series(dtype=float)

        total_len = len(self.returns)
        if total_len < train_window + test_window:
            return {
                "meta": {"error": f"insufficient data: {total_len} rows"},
                "results": results,
            }

        def turnover(prev: pd.Series, curr: pd.Series) -> float:
            idx = prev.index.union(curr.index)
            p = prev.reindex(idx).fillna(0.0)
            c = curr.reindex(idx).fillna(0.0)
            return float(np.abs(c - p).sum() / 2.0)

        for start_idx in range(0, total_len - train_window - test_window + 1, step_size):
            train_end = start_idx + train_window
            test_end = train_end + test_window

            train_data = self.returns.iloc[start_idx:train_end]
            test_data = self.returns.iloc[train_end:test_end]

            stats_df = self._audit_training_stats(train_data)
            clusters = self._cluster_data(train_data)
            regime = self.detector.detect_regime(train_data)[0]

            # --- WEIGHT CACHING ---
            # Optimization happens once per (engine, profile)
            cached_weights: Dict[tuple[str, str], pd.DataFrame] = {}

            custom_optimizer = None
            if "custom" in engines and "custom" in available_engines:
                custom_optimizer = self._init_optimizer(train_data, clusters, stats_df)

            for eng in engines:
                if eng not in available_engines:
                    continue
                for prof in profiles:
                    try:
                        if eng == "custom" and custom_optimizer is not None:
                            p_norm = self._normalize_profile(prof)
                            if p_norm == "barbell":
                                weights_df = custom_optimizer.run_barbell(cluster_cap=cluster_cap)
                            else:
                                method_map = {"min_variance": "min_var", "risk_parity": "risk_parity", "max_sharpe": "max_sharpe"}
                                opt_method = method_map.get(p_norm, p_norm)
                                weights_df = custom_optimizer.run_profile(p_norm, opt_method, cluster_cap=cluster_cap)
                        else:
                            weights_df = self._compute_weights(train_data=train_data, clusters=clusters, stats_df=stats_df, profile=prof, engine=eng, cluster_cap=cluster_cap)

                        if not weights_df.empty:
                            cached_weights[(eng, prof)] = weights_df
                    except Exception as e:
                        # Error during optimization is shared across all simulators
                        for s in sim_names:
                            results[s][eng][prof].setdefault("errors", []).append(f"Opt Error: {str(e)}")

            # --- MULTI-SIMULATOR EVALUATION ---
            for s_name in sim_names:
                simulator = build_simulator(s_name)
                for (eng, prof), weights_df in cached_weights.items():
                    try:
                        perf = simulator.simulate(test_data, weights_df)

                        weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
                        w_series = weights_df.set_index("Symbol")[weight_col].astype(float).fillna(0.0)
                        normalizer = float(w_series.abs().sum()) if weight_col == "Net_Weight" else float(w_series.sum())
                        if normalizer > 0:
                            w_series = w_series / (normalizer + 1e-12)

                        prev = prev_weights.get((s_name, eng, prof))
                        t_val = turnover(prev, w_series) if prev is not None and normalizer > 0 else None
                        if normalizer > 0:
                            prev_weights[(s_name, eng, prof)] = w_series

                        top_cols = ["Symbol", "Weight"]
                        for extra in ["Net_Weight", "Direction", "Cluster_ID"]:
                            if extra in weights_df.columns:
                                top_cols.append(extra)

                        window_res = {
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
                            "var_95": perf.get("var_95"),
                            "cvar_95": perf.get("cvar_95"),
                            "n_assets": int(len(weights_df)),
                            "turnover": t_val,
                            "top_assets": cast(Any, weights_df.head(5)[top_cols]).to_dict(orient="records"),
                        }

                        results[s_name][eng][prof]["windows"].append(window_res)

                        if cumulative[(s_name, eng, prof)].empty:
                            cumulative[(s_name, eng, prof)] = perf["daily_returns"]
                        else:
                            cumulative[(s_name, eng, prof)] = pd.concat([cumulative[(s_name, eng, prof)], perf["daily_returns"]])

                    except Exception as e:
                        results[s_name][eng][prof].setdefault("errors", []).append(f"Sim Error ({s_name}): {str(e)}")

        # Summaries
        for s_name in sim_names:
            for eng, prof_map in results[s_name].items():
                if prof_map.get("_status", {}).get("skipped"):
                    continue
                for prof in profiles:
                    windows = prof_map.get(prof, {}).get("windows", [])
                    if not windows:
                        continue
                    summary = self._summarize_results(windows, cumulative[(s_name, eng, prof)])
                    t_vals = [w.get("turnover") for w in windows if w.get("turnover") is not None]
                    summary["avg_turnover"] = float(np.mean(t_vals)) if t_vals else None
                    prof_map[prof]["summary"] = summary

        return {
            "meta": {
                "train_window": train_window,
                "test_window": test_window,
                "step_size": step_size,
                "cluster_cap": cluster_cap,
                "profiles": profiles,
                "engines": engines,
                "simulators": sim_names,
                "generated_at": str(pd.Timestamp.now()),
            },
            "results": results,
            "returns": {f"{s}_{e}_{p}": v for (s, e, p), v in cumulative.items() if not v.empty},
        }

    def _cluster_data(self, df: pd.DataFrame) -> Dict[str, List[str]]:
        import scipy.cluster.hierarchy as sch
        from scipy.spatial.distance import squareform

        get_robust_correlation = importlib.import_module("scripts.natural_selection").get_robust_correlation
        corr = get_robust_correlation(df)
        dist = np.sqrt(0.5 * (1 - corr.values.clip(-1, 1)))
        dist = (dist + dist.T) / 2
        np.fill_diagonal(dist, 0)

        condensed = squareform(dist, checks=False)
        link = sch.linkage(condensed, method="ward")
        cluster_ids = sch.fcluster(link, t=10, criterion="maxclust")  # Simplified for backtest

        clusters = {}
        for sym, c_id in zip(df.columns, cluster_ids):
            c_id_str = str(c_id)
            if c_id_str not in clusters:
                clusters[c_id_str] = []
            clusters[c_id_str].append(str(sym))
        return clusters

    def _init_optimizer(self, train_data: pd.DataFrame, clusters: Dict[str, List[str]], stats_df: pd.DataFrame):
        # We need to save temporary files because ClusteredOptimizerV2 reads from paths
        tmp_returns = "data/lakehouse/tmp_bt_returns.pkl"
        tmp_clusters = "data/lakehouse/tmp_bt_clusters.json"
        tmp_stats = "data/lakehouse/tmp_bt_stats.json"

        train_data.to_pickle(tmp_returns)
        with open(tmp_clusters, "w") as f:
            json.dump(clusters, f)

        # Explicitly reset index and ensure column names match what Optimizer expects
        stats_export = stats_df.copy()
        if "Symbol" not in stats_export.columns:
            stats_export = stats_export.reset_index().rename(columns={"index": "Symbol"})

        stats_export.to_json(tmp_stats, orient="records")

        optimizer_cls = importlib.import_module("scripts.optimize_clustered_v2").ClusteredOptimizerV2
        return optimizer_cls(returns_path=tmp_returns, clusters_path=tmp_clusters, meta_path="data/lakehouse/portfolio_meta.json", stats_path=tmp_stats)

    def _normalize_profile(self, profile: str) -> str:
        p = (profile or "").strip().lower()
        if p == "hrp":
            return "risk_parity"
        return p

    def _compute_weights(
        self,
        *,
        train_data: pd.DataFrame,
        clusters: Dict[str, List[str]],
        stats_df: pd.DataFrame,
        profile: str,
        engine: str,
        cluster_cap: float,
    ) -> pd.DataFrame:
        profile_norm = self._normalize_profile(profile)
        engine_norm = (engine or "").strip().lower()

        if engine_norm == "custom":
            optimizer = self._init_optimizer(train_data, clusters, stats_df)

            # Map profile names to optimizer methods
            method_map = {"min_variance": "min_var", "risk_parity": "risk_parity", "max_sharpe": "max_sharpe"}

            if profile_norm == "barbell":
                return optimizer.run_barbell(cluster_cap=cluster_cap)

            opt_method = method_map.get(profile_norm, profile_norm)
            return optimizer.run_profile(profile_norm, opt_method, cluster_cap=cluster_cap)

        # External engines operate on in-memory returns + cluster structure.
        req_profile = "hrp" if profile_norm == "risk_parity" else profile_norm
        if req_profile not in {"min_variance", "hrp", "max_sharpe", "barbell"}:
            raise ValueError(f"Unsupported profile: {profile}")

        request = EngineRequest(profile=req_profile, cluster_cap=cluster_cap)
        eng = build_engine(engine_norm)
        response = eng.optimize(returns=train_data, clusters=clusters, meta=cast(dict, self.meta), stats=stats_df, request=request)
        return response.weights

    def _summarize_results(self, results: List[Dict], cumulative_returns: pd.Series) -> Dict:
        from tradingview_scraper.utils.metrics import calculate_performance_metrics

        rets = [r["returns"] for r in results]
        vols = [r["vol"] for r in results]
        sharpes = [r["sharpe"] for r in results]

        cvars: List[float] = []
        for r in results:
            cvar_val = r.get("cvar_95")
            if cvar_val is None:
                continue
            try:
                cvars.append(float(cvar_val))
            except Exception:
                continue

        avg_window_cvar_95 = float(np.mean(cvars)) if cvars else None

        # Standard summary using QuantStats via unified helper
        summary = calculate_performance_metrics(cumulative_returns)

        # Merge with window-specific metrics
        summary.update(
            {
                "total_cumulative_return": summary["total_return"],
                "annualized_return": summary["annualized_return"] if "annualized_return" in summary else (cumulative_returns.mean() * 252 if not cumulative_returns.empty else 0.0),
                "annualized_vol": summary["realized_vol"],
                "avg_window_return": float(np.mean(rets)),
                "avg_window_vol": float(np.mean(vols)),
                "avg_window_sharpe": float(np.mean(sharpes)),
                "avg_window_cvar_95": avg_window_cvar_95,
                "realized_var_95": summary["var_95"],
                "realized_cvar_95": summary["cvar_95"],
                "win_rate": float(np.mean([1 if r > 0 else 0 for r in rets])),
            }
        )
        return summary


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, default="risk_parity", choices=["risk_parity", "hrp", "min_variance", "max_sharpe", "barbell"])
    parser.add_argument("--engine", type=str, default="custom")
    parser.add_argument("--train", type=int, default=120)
    parser.add_argument("--test", type=int, default=20)
    parser.add_argument("--step", type=int, default=20)
    parser.add_argument("--cluster-cap", type=float, default=float(os.getenv("CLUSTER_CAP", "0.25")))
    parser.add_argument("--simulators", type=str, default="custom", help="Comma-separated simulators (custom, cvxportfolio)")
    parser.add_argument("--simulator", type=str, default="custom", choices=["custom", "cvxportfolio"])

    parser.add_argument("--tournament", action="store_true")
    parser.add_argument("--engines", type=str, default="custom,skfolio,riskfolio,pyportfolioopt,cvxportfolio")
    parser.add_argument("--profiles", type=str, default="min_variance,hrp,max_sharpe,barbell")
    parser.add_argument("--list-engines", action="store_true")
    args = parser.parse_args()

    if args.list_engines:
        print("Known engines:", ", ".join(list_known_engines()))
        print("Available engines:", ", ".join(list_available_engines()))
        return

    bt = BacktestEngine()
    output_dir = get_settings().prepare_summaries_run_dir()

    if args.tournament:
        engines = [e.strip().lower() for e in (args.engines or "").split(",") if e.strip()]
        profiles = [p.strip().lower() for p in (args.profiles or "").split(",") if p.strip()]
        sims = [s.strip().lower() for s in (args.simulators or "").split(",") if s.strip()]

        full_results = bt.run_tournament(
            train_window=args.train,
            test_window=args.test,
            step_size=args.step,
            profiles=profiles,
            engines=engines,
            cluster_cap=float(args.cluster_cap),
            simulators=sims,
        )
        res = full_results["results"]
        output_file = output_dir / "tournament_results.json"
        with open(output_file, "w") as f:
            json.dump({"meta": full_results["meta"], "results": res}, f, indent=2)
        print(f"\nTournament results saved to {output_file}")

        # Save cumulative returns for tearsheets
        if "returns" in full_results:
            returns_dir = output_dir / "returns"
            returns_dir.mkdir(exist_ok=True)
            for key, series in full_results["returns"].items():
                series.to_pickle(returns_dir / f"{key}.pkl")
            print(f"Cumulative returns exported to {returns_dir}")
        return

    profile_slug = "risk_parity" if args.profile == "hrp" else args.profile
    bt_results = bt.run_walk_forward(
        train_window=args.train,
        test_window=args.test,
        step_size=args.step,
        profile=profile_slug,
        engine=args.engine,
        cluster_cap=float(args.cluster_cap),
        simulator_name=args.simulator,
    )

    if not bt_results:
        logger.error("No backtest results produced.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print(f"BACKTEST SUMMARY: {args.engine.upper()} / {profile_slug.upper()}")
    print("=" * 50)
    for k, v in bt_results["summary"].items():
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v_str = "N/A"
            else:
                v_str = f"{float(v):.4f}"
        except Exception:
            v_str = str(v)
        print(f"{k:25}: {v_str}")

    suffix = "" if args.engine.strip().lower() == "custom" else f"_{args.engine.strip().lower()}"
    output_file = output_dir / f"backtest_{profile_slug}{suffix}.json"
    with open(output_file, "w") as f:
        json.dump(bt_results, f, indent=2)
    print(f"\nDetailed results saved to {output_file}")


if __name__ == "__main__":
    main()
