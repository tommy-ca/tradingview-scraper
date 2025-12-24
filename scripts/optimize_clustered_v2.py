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
            if c_weight < 1e-6:
                continue
            c_id = str(c_col).replace("Cluster_", "")
            intra_w = self.intra_cluster_weights[c_id]
            for sym, sym_w_in_cluster in intra_w.items():
                if sym_w_in_cluster * c_weight < 1e-6:
                    continue
                final_alloc.append(
                    {
                        "Symbol": sym,
                        "Cluster_ID": c_id,
                        "Cluster_Label": f"Cluster {c_id}",
                        "Weight": float(c_weight * sym_w_in_cluster),
                        "Cluster_Weight": float(c_weight),
                        "Intra_Cluster_Weight": float(sym_w_in_cluster),
                        "Direction": self.meta.get(str(sym), {}).get("direction", "LONG"),
                        "Market": self.meta.get(str(sym), {}).get("market", "UNKNOWN"),
                    }
                )

        return pd.DataFrame(final_alloc).sort_values("Weight", ascending=False)

    def run_barbell(self, cluster_cap: float = 0.20) -> pd.DataFrame:
        logger.info(f"Running profile: Antifragile Barbell (Clustered Aggressors, Core Cap: {cluster_cap})")
        if self.stats is None:
            logger.error("No antifragility stats found for barbell.")
            return pd.DataFrame()

        # 1. IDENTIFY AGGRESSOR CLUSTERS
        # Map symbols to clusters in stats
        symbol_to_cluster = {}
        for c_id, symbols in self.clusters.items():
            for s in symbols:
                symbol_to_cluster[s] = c_id

        stats_with_clusters = self.stats.copy()
        stats_with_clusters["Cluster_ID"] = stats_with_clusters["Symbol"].apply(lambda x: symbol_to_cluster.get(str(x)))

        # Calculate best asset per cluster
        cluster_convexity = stats_with_clusters.sort_values("Antifragility_Score", ascending=False).groupby("Cluster_ID").first()
        top_aggressor_clusters = cluster_convexity.sort_values("Antifragility_Score", ascending=False).head(5)

        agg_symbols = top_aggressor_clusters["Symbol"].tolist()
        agg_cluster_ids = top_aggressor_clusters.index.tolist()

        agg_weight_total = 0.10
        agg_weight_per = agg_weight_total / len(agg_symbols)

        # 2. OPTIMIZE CORE (90%)
        # Exclude all symbols from the Aggressor Clusters to prevent correlated core risk
        excluded_symbols = []
        for c_id in agg_cluster_ids:
            excluded_symbols.extend(self.clusters[str(c_id)])

        original_returns = self.returns
        available_core_symbols = [s for s in pd.Index(self.returns.columns) if s not in excluded_symbols]
        self.returns = self.returns[available_core_symbols]

        # Re-benchmark without excluded clusters
        self.cluster_benchmarks = pd.DataFrame()
        self.intra_cluster_weights = {}
        for c_id, symbols in self.clusters.items():
            if int(c_id) in agg_cluster_ids:
                continue

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
            c_id = symbol_to_cluster.get(sym)
            final_alloc.append(
                {
                    "Symbol": sym,
                    "Cluster_ID": str(c_id),
                    "Cluster_Label": f"Cluster {c_id} (AGGRESSOR)",
                    "Weight": float(agg_weight_per),
                    "Cluster_Weight": float(agg_weight_per),
                    "Type": "AGGRESSOR (Antifragile)",
                    "Direction": self.meta.get(str(sym), {}).get("direction", "LONG"),
                    "Market": self.meta.get(str(sym), {}).get("market", "UNKNOWN"),
                }
            )

        # Add Core
        for c_col, c_weight in core_cluster_weights.items():
            if c_weight < 1e-6:
                continue
            c_id = str(c_col).replace("Cluster_", "")
            intra_w = self.intra_cluster_weights[c_id]
            for sym, sym_w_in_cluster in intra_w.items():
                if sym_w_in_cluster * c_weight < 1e-6:
                    continue
                final_alloc.append(
                    {
                        "Symbol": sym,
                        "Cluster_ID": c_id,
                        "Cluster_Label": f"Cluster {c_id}",
                        "Weight": float(c_weight * sym_w_in_cluster * 0.90),
                        "Cluster_Weight": float(c_weight * 0.90),
                        "Type": "CORE (Safe)",
                        "Direction": self.meta.get(str(sym), {}).get("direction", "LONG"),
                        "Market": self.meta.get(str(sym), {}).get("market", "UNKNOWN"),
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

    # Prepare clusters metadata for implementation
    cluster_metadata = {}
    for c_id, symbols in opt.clusters.items():
        valid_symbols = [s for s in symbols if s in opt.returns.columns]
        if not valid_symbols:
            continue
        cluster_metadata[c_id] = {
            "symbols": valid_symbols,
            "size": len(valid_symbols),
            "markets": list(set(opt.meta.get(s, {}).get("market", "UNKNOWN") for s in valid_symbols)),
        }

    # Save all
    output = {"profiles": {}, "clusters": cluster_metadata}
    for name, df in profiles.items():
        output["profiles"][name] = df.to_dict(orient="records")
        print(f"\n--- {name.upper()} PROFILE ---")
        print(df.head(10).to_string(index=False))

    with open("data/lakehouse/portfolio_optimized_v2.json", "w") as f:
        json.dump(output, f, indent=2)

    logger.info("Saved all profiles to data/lakehouse/portfolio_optimized_v2.json")


if __name__ == "__main__":
    main()
