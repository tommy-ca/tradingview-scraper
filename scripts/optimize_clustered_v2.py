import json
import logging
import os
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("clustered_optimizer_v2")


class ClusteredOptimizerV2:
    def __init__(self, returns_path: str, clusters_path: str, meta_path: str, stats_path: Optional[str] = None):
        # Explicitly cast to DataFrame to satisfy linter
        self.returns = cast(pd.DataFrame, pd.read_pickle(returns_path))
        with open(clusters_path, "r") as f:
            self.clusters = cast(Dict[str, List[str]], json.load(f))
        with open(meta_path, "r") as f:
            self.meta = cast(Dict[str, Any], json.load(f))
        self.stats = None
        if stats_path and os.path.exists(stats_path):
            with open(stats_path, "r") as f:
                self.stats = cast(pd.DataFrame, pd.read_json(f))

        # Ensure returns matches clusters
        all_symbols = [s for c in self.clusters.values() for s in c]
        available_symbols = [s for s in all_symbols if s in self.returns.columns]
        self.returns = self.returns[available_symbols].fillna(0.0)

        # Build cluster benchmarks (Inverse-Variance weights within cluster)
        self.cluster_benchmarks = pd.DataFrame()
        self.intra_cluster_weights = {}  # ClusterID -> Series of weights summing to 1

        for c_id, symbols in self.clusters.items():
            valid_symbols = [s for s in symbols if s in self.returns.columns]
            if not valid_symbols:
                continue

            sub_rets = self.returns[valid_symbols]
            if len(valid_symbols) == 1:
                self.cluster_benchmarks[f"Cluster_{c_id}"] = pd.DataFrame(sub_rets).iloc[:, 0]
                self.intra_cluster_weights[c_id] = pd.Series([1.0], index=valid_symbols)
            else:
                # Inverse Variance Weighting within cluster
                vols = sub_rets.std() * np.sqrt(252)
                inv_vars = 1.0 / (vols**2 + 1e-9)
                w = inv_vars / inv_vars.sum()
                self.cluster_benchmarks[f"Cluster_{c_id}"] = (sub_rets * w).sum(axis=1)
                self.intra_cluster_weights[c_id] = w

    def _get_cov(self, df: pd.DataFrame):
        return df.cov() * 252

    def _min_var_obj(self, weights, cov):
        return np.sqrt(np.dot(weights.T, np.dot(cov, weights)))

    def _risk_parity_obj(self, weights, cov):
        vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
        if vol == 0:
            return 0
        mrc = np.dot(cov, weights) / vol
        rc = weights * mrc
        target_rc = vol / len(weights)
        return np.sum(np.square(rc - target_rc))

    def _max_sharpe_obj(self, weights, returns_df: pd.DataFrame):
        cov = self._get_cov(returns_df)
        vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
        ret = np.sum(returns_df.mean() * weights) * 252
        if vol == 0:
            return 0
        return -(ret / vol)

    def optimize_across_clusters(self, method: str, cluster_cap: float = 0.25) -> pd.Series:
        n = self.cluster_benchmarks.shape[1]
        init_weights = np.array([1.0 / n] * n)
        # Enforce cluster_cap (e.g. 0.25)
        bounds = tuple((0.0, cluster_cap) for _ in range(n))
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        cov = self._get_cov(self.cluster_benchmarks)

        if method == "min_var":
            res = minimize(self._min_var_obj, init_weights, args=(cov,), method="SLSQP", bounds=bounds, constraints=constraints)
        elif method == "risk_parity":
            res = minimize(self._risk_parity_obj, init_weights, args=(cov,), method="SLSQP", bounds=bounds, constraints=constraints)
        elif method == "max_sharpe":
            res = minimize(self._max_sharpe_obj, init_weights, args=(self.cluster_benchmarks,), method="SLSQP", bounds=bounds, constraints=constraints)
        else:
            raise ValueError(f"Unknown method {method}")

        return pd.Series(res.x, index=self.cluster_benchmarks.columns)

    def run_profile(self, name: str, across_method: str, cluster_cap: float = 0.25) -> pd.DataFrame:
        logger.info(f"Running profile: {name} (Across: {across_method}, Cap: {cluster_cap})")
        cluster_weights = self.optimize_across_clusters(across_method, cluster_cap=cluster_cap)

        final_alloc = []
        for c_col, c_weight in cluster_weights.items():
            c_id = str(c_col).replace("Cluster_", "")
            intra_w = self.intra_cluster_weights[c_id]
            for sym, sym_w_in_cluster in intra_w.items():
                final_alloc.append(
                    {
                        "Symbol": sym,
                        "Cluster": f"Cluster {c_id}",
                        "Weight": c_weight * sym_w_in_cluster,
                        "Cluster_Weight": c_weight,
                        "Direction": self.meta.get(str(sym), {}).get("direction", "LONG"),
                    }
                )

        return pd.DataFrame(final_alloc).sort_values("Weight", ascending=False)

    def run_barbell(self, cluster_cap: float = 0.20) -> pd.DataFrame:
        logger.info(f"Running profile: Antifragile Barbell (Clustered Core, Cap: {cluster_cap})")
        if self.stats is None:
            logger.error("No antifragility stats found for barbell.")
            return pd.DataFrame()

        # 10% Aggressors
        aggressors = self.stats.sort_values("Antifragility_Score", ascending=False).head(5)
        agg_symbols = set(aggressors["Symbol"].tolist())
        agg_weight_total = 0.10
        agg_weight_per = agg_weight_total / len(agg_symbols)

        # 90% Core (using Clustered Risk Parity)
        original_returns = self.returns
        available_core_symbols = [s for s in pd.Index(self.returns.columns) if s not in agg_symbols]
        self.returns = self.returns[available_core_symbols]

        # Re-benchmark without aggressors
        self.cluster_benchmarks = pd.DataFrame()
        self.intra_cluster_weights = {}
        for c_id, symbols in self.clusters.items():
            valid_symbols = [s for s in symbols if s in self.returns.columns]
            if not valid_symbols:
                continue
            sub_rets = self.returns[valid_symbols]
            if len(valid_symbols) == 1:
                self.cluster_benchmarks[f"Cluster_{c_id}"] = pd.DataFrame(sub_rets).iloc[:, 0]
                self.intra_cluster_weights[c_id] = pd.Series([1.0], index=valid_symbols)
            else:
                vols = sub_rets.std() * np.sqrt(252)
                inv_vars = 1.0 / (vols**2 + 1e-9)
                w = inv_vars / inv_vars.sum()
                self.cluster_benchmarks[f"Cluster_{c_id}"] = (sub_rets * w).sum(axis=1)
                self.intra_cluster_weights[c_id] = w

        core_cluster_weights = self.optimize_across_clusters("risk_parity", cluster_cap=cluster_cap)

        final_alloc = []
        # Add Aggressors
        for sym in agg_symbols:
            final_alloc.append({"Symbol": sym, "Cluster": "AGGRESSOR", "Weight": agg_weight_per, "Type": "AGGRESSOR (Antifragile)", "Direction": self.meta.get(str(sym), {}).get("direction", "LONG")})

        # Add Core
        for c_col, c_weight in core_cluster_weights.items():
            c_id = str(c_col).replace("Cluster_", "")
            intra_w = self.intra_cluster_weights[c_id]
            for sym, sym_w_in_cluster in intra_w.items():
                final_alloc.append(
                    {
                        "Symbol": sym,
                        "Cluster": f"Cluster {c_id}",
                        "Weight": float(c_weight * sym_w_in_cluster * 0.90),
                        "Type": "CORE (Safe)",
                        "Direction": self.meta.get(str(sym), {}).get("direction", "LONG"),
                    }
                )

        self.returns = original_returns  # Restore
        return pd.DataFrame(final_alloc).sort_values("Weight", ascending=False)


def main():
    opt = ClusteredOptimizerV2(
        returns_path="data/lakehouse/portfolio_returns.pkl",
        clusters_path="data/lakehouse/portfolio_clusters.json",
        meta_path="data/lakehouse/portfolio_meta.json",
        stats_path="data/lakehouse/antifragility_stats.json",
    )

    profiles = {
        "min_variance": opt.run_profile("Min Variance", "min_var"),
        "risk_parity": opt.run_profile("Risk Parity", "risk_parity"),
        "max_sharpe": opt.run_profile("Max Sharpe", "max_sharpe"),
        "barbell": opt.run_barbell(),
    }

    # Save all
    output = {}
    for name, df in profiles.items():
        output[name] = df.to_dict(orient="records")
        print(f"\n--- {name.upper()} PROFILE ---")
        print(df.head(10).to_string(index=False))

    with open("data/lakehouse/portfolio_optimized_v2.json", "w") as f:
        json.dump(output, f, indent=2)

    logger.info("Saved all profiles to data/lakehouse/portfolio_optimized_v2.json")


if __name__ == "__main__":
    main()
