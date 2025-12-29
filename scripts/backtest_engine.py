import importlib
import json
import logging
import os
import sys
from typing import Dict, List, cast

import numpy as np
import pandas as pd

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

    def run_walk_forward(self, train_window: int = 120, test_window: int = 20, step_size: int = 20, profile: str = "risk_parity"):
        logger.info(f"Starting Walk-Forward Backtest (Profile: {profile})")
        logger.info(f"Train: {train_window}d, Test: {test_window}d, Step: {step_size}d")

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
            optimizer = self._init_optimizer(train_data, clusters, stats_df)

            # Map profile names to optimizer methods
            method_map = {"min_variance": "min_var", "risk_parity": "risk_parity", "max_sharpe": "max_sharpe"}

            if profile == "barbell":
                weights_df = optimizer.run_barbell()
            else:
                opt_method = method_map.get(profile, profile)
                weights_df = optimizer.run_profile(profile, opt_method)

            if weights_df.empty:
                logger.warning(f"No weights generated for window {start_idx}")
                continue

            # 3. Calculate Performance on Test Data
            test_perf = self._evaluate_performance(test_data, weights_df)

            window_res = {
                "start_date": str(test_data.index[0]),
                "end_date": str(test_data.index[-1]),
                "regime": self.detector.detect_regime(train_data)[0],
                "returns": test_perf["total_return"],
                "vol": test_perf["realized_vol"],
                "sharpe": test_perf["sharpe"],
                "max_drawdown": test_perf["max_drawdown"],
                "n_assets": len(weights_df),
                "top_assets": weights_df.head(5)[["Symbol", "Weight"]].to_dict(orient="records"),
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

    def _evaluate_performance(self, test_data: pd.DataFrame, weights_df: pd.DataFrame) -> Dict:
        # Align weights and test data
        weights_series = weights_df.set_index("Symbol")["Weight"]
        symbols = [s for s in weights_series.index if s in test_data.columns]

        if not symbols:
            return {"total_return": 0, "realized_vol": 0, "sharpe": 0, "max_drawdown": 0, "daily_returns": pd.Series()}

        # Re-normalize weights for available symbols
        w = weights_series[symbols]
        w = w / w.sum()

        daily_returns = (test_data[symbols] * w.values).sum(axis=1)

        total_return = (1 + daily_returns).prod() - 1
        realized_vol = daily_returns.std() * np.sqrt(252)

        sharpe = (daily_returns.mean() * 252) / (realized_vol + 1e-9)

        cum_ret = (1 + daily_returns).cumprod()
        running_max = cum_ret.cummax()
        drawdown = (cum_ret - running_max) / running_max
        max_drawdown = float(drawdown.min())

        return {"total_return": float(total_return), "realized_vol": float(realized_vol), "sharpe": float(sharpe), "max_drawdown": max_drawdown, "daily_returns": daily_returns}

    def _summarize_results(self, results: List[Dict], cumulative_returns: pd.Series) -> Dict:
        rets = [r["returns"] for r in results]
        vols = [r["vol"] for r in results]
        sharpes = [r["sharpe"] for r in results]

        total_cum_return = (1 + cumulative_returns).cumprod().iloc[-1] - 1 if not cumulative_returns.empty else 0
        annualized_return = cumulative_returns.mean() * 252
        annualized_vol = cumulative_returns.std() * np.sqrt(252)

        return {
            "total_cumulative_return": float(total_cum_return),
            "annualized_return": float(annualized_return),
            "annualized_vol": float(annualized_vol),
            "avg_window_return": float(np.mean(rets)),
            "avg_window_vol": float(np.mean(vols)),
            "avg_window_sharpe": float(np.mean(sharpes)),
            "win_rate": float(np.mean([1 if r > 0 else 0 for r in rets])),
        }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=str, default="risk_parity", choices=["risk_parity", "min_variance", "max_sharpe", "barbell"])
    parser.add_argument("--train", type=int, default=120)
    parser.add_argument("--test", type=int, default=20)
    parser.add_argument("--step", type=int, default=20)
    args = parser.parse_args()

    engine = BacktestEngine()
    bt_results = engine.run_walk_forward(train_window=args.train, test_window=args.test, step_size=args.step, profile=args.profile)

    if not bt_results:
        logger.error("No backtest results produced.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print(f"BACKTEST SUMMARY: {args.profile.upper()}")
    print("=" * 50)
    for k, v in bt_results["summary"].items():
        print(f"{k:25}: {v:.4f}")

    output_dir = get_settings().prepare_summaries_run_dir()
    output_file = output_dir / f"backtest_{args.profile}.json"
    with open(output_file, "w") as f:
        json.dump(bt_results, f, indent=2)
    print(f"\nDetailed results saved to {output_file}")


if __name__ == "__main__":
    main()
