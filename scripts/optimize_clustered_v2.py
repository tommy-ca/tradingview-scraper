import json
import logging
import os
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("clustered_optimizer_v2")

AUDIT_FILE = "data/lakehouse/selection_audit.json"


class ClusteredOptimizerV2:
    def __init__(self, returns_path: str, clusters_path: str, meta_path: str, stats_path: Optional[str] = None):
        # Explicitly cast to DataFrame to satisfy linter
        with open(returns_path, "rb") as f_in:
            self.returns = cast(pd.DataFrame, pd.read_pickle(f_in))

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

        # Build cluster benchmarks and aggregate risk stats
        self.cluster_benchmarks = pd.DataFrame()
        self.intra_cluster_weights = {}  # ClusterID -> Series of weights summing to 1
        self.cluster_stats = {}  # ClusterID -> Aggregated stats

        for c_id, symbols in self.clusters.items():
            valid_symbols = [s for s in symbols if s in self.returns.columns]
            if not valid_symbols:
                continue

            sub_rets = self.returns[valid_symbols]

            # 1. Hybrid Layer 2 Weighting (Blend of InvVar and AlphaRank)
            vols = sub_rets.std() * np.sqrt(252)
            inv_vars = 1.0 / (vols**2 + 1e-9)
            w_ivp = inv_vars / inv_vars.sum()

            # Alpha components for internal weighting
            mom = sub_rets.mean() * 252

            def norm(s):
                return (s - s.min()) / (s.max() - s.min() + 1e-9) if len(s) > 1 else pd.Series(1.0, index=s.index)

            # Use Alpha scores for within-cluster ranking
            w_alpha = norm(mom) / (norm(mom).sum() + 1e-9)

            # 50/50 Blend
            w_hybrid = 0.5 * w_ivp + 0.5 * w_alpha
            w_hybrid = w_hybrid / w_hybrid.sum()

            self.cluster_benchmarks[f"Cluster_{c_id}"] = (sub_rets * w_hybrid).sum(axis=1)
            self.intra_cluster_weights[c_id] = w_hybrid

            # 2. Aggregate cluster fragility (CVaR)
            if self.stats is not None:
                c_af_stats = self.stats[self.stats["Symbol"].isin(valid_symbols)]
                if not c_af_stats.empty:
                    # Use mean Fragility Score as penalty factor
                    self.cluster_stats[c_id] = {"fragility": float(c_af_stats["Fragility_Score"].mean()), "cvar": float(c_af_stats["CVaR_95"].mean())}
                else:
                    self.cluster_stats[c_id] = {"fragility": 1.0, "cvar": -0.05}
            else:
                self.cluster_stats[c_id] = {"fragility": 1.0, "cvar": -0.05}

    def _get_cov(self, df: pd.DataFrame):
        return df.cov() * 252

    def _min_var_obj(self, weights, cov, penalties=None):
        base_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
        if penalties is not None:
            # Penalize by weighted average fragility
            penalty = np.dot(weights, penalties)
            return base_vol * (1.0 + penalty * 0.2)
        return base_vol

    def _risk_parity_obj(self, weights, cov):
        vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
        if vol == 0:
            return 0
        mrc = np.dot(cov, weights) / vol
        rc = weights * mrc
        target_rc = vol / len(weights)
        return np.sum(np.square(rc - target_rc))

    def _max_sharpe_obj(self, weights, returns_df: pd.DataFrame, penalties=None):
        cov = self._get_cov(returns_df)
        vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
        ret = np.sum(returns_df.mean() * weights) * 252
        if vol == 0:
            return 0
        sharpe = ret / vol
        if penalties is not None:
            penalty = np.dot(weights, penalties)
            return -(sharpe / (1.0 + penalty * 0.2))
        return -sharpe

    def optimize_across_clusters(self, method: str, cluster_cap: float = 0.25) -> pd.Series:
        n = self.cluster_benchmarks.shape[1]
        init_weights = np.array([1.0 / n] * n)
        bounds = tuple((0.0, cluster_cap) for _ in range(n))
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        cov = self._get_cov(self.cluster_benchmarks)

        penalties = np.array([self.cluster_stats[c_col.replace("Cluster_", "")]["fragility"] for c_col in self.cluster_benchmarks.columns])

        if method == "min_var":
            res = minimize(self._min_var_obj, init_weights, args=(cov, penalties), method="SLSQP", bounds=bounds, constraints=constraints)
        elif method == "risk_parity":
            res = minimize(self._risk_parity_obj, init_weights, args=(cov,), method="SLSQP", bounds=bounds, constraints=constraints)
        elif method == "max_sharpe":
            res = minimize(self._max_sharpe_obj, init_weights, args=(self.cluster_benchmarks, penalties), method="SLSQP", bounds=bounds, constraints=constraints)
        else:
            raise ValueError(f"Unknown method {method}")

        return pd.Series(res.x, index=self.cluster_benchmarks.columns)

    def run_profile(self, name: str, across_method: str, cluster_cap: float = 0.25, top_n: int = 0) -> pd.DataFrame:
        logger.info(f"Running profile: {name} (Across: {across_method}, Cap: {cluster_cap}, Top N: {top_n or 'ALL'})")
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

                direction = self.meta.get(str(sym), {}).get("direction", "LONG")
                final_alloc.append(
                    {
                        "Symbol": sym,
                        "Description": self.meta.get(str(sym), {}).get("description", "N/A"),
                        "Sector": self.meta.get(str(sym), {}).get("sector", "N/A"),
                        "Cluster_ID": c_id,
                        "Cluster_Label": f"Cluster {c_id}",
                        "Weight": float(c_weight * sym_w_in_cluster),
                        "Cluster_Weight": float(c_weight),
                        "Intra_Cluster_Weight": float(sym_w_in_cluster),
                        "Direction": direction,
                        "Market": self.meta.get(str(sym), {}).get("market", "UNKNOWN"),
                        "Net_Weight": float(c_weight * sym_w_in_cluster) * (1.0 if direction == "LONG" else -1.0),
                    }
                )

        df = pd.DataFrame(final_alloc).sort_values("Weight", ascending=False)
        if top_n > 0:
            df = df.head(top_n)
        return df

    def run_barbell(self, cluster_cap: float = 0.25, top_n: int = 0) -> pd.DataFrame:
        logger.info(f"Running profile: Antifragile Barbell (Clustered Aggressors, Core Cap: {cluster_cap}, Top N: {top_n or 'ALL'})")
        if self.stats is None:
            logger.error("No antifragility stats found for barbell.")
            return pd.DataFrame()

        symbol_to_cluster = {}
        for c_id, symbols in self.clusters.items():
            for s in symbols:
                symbol_to_cluster[s] = c_id

        stats_with_clusters = self.stats.copy()
        stats_with_clusters["Cluster_ID"] = stats_with_clusters["Symbol"].apply(lambda x: symbol_to_cluster.get(str(x)))

        cluster_convexity = stats_with_clusters.sort_values("Antifragility_Score", ascending=False).groupby("Cluster_ID").first()
        top_aggressor_clusters = cluster_convexity.sort_values("Antifragility_Score", ascending=False).head(5)

        agg_symbols = top_aggressor_clusters["Symbol"].tolist()
        agg_cluster_ids = top_aggressor_clusters.index.tolist()

        agg_weight_total = 0.10
        agg_weight_per = agg_weight_total / len(agg_symbols)

        excluded_symbols = []
        for c_id in agg_cluster_ids:
            excluded_symbols.extend(self.clusters[str(c_id)])

        original_returns = self.returns
        available_core_symbols = [s for s in pd.Index(self.returns.columns) if s not in excluded_symbols]
        self.returns = self.returns[available_core_symbols]

        self.cluster_benchmarks = pd.DataFrame()
        self.intra_cluster_weights = {}
        for c_id, symbols in self.clusters.items():
            if str(c_id) in [str(x) for x in agg_cluster_ids]:
                continue
            valid_symbols = [s for s in symbols if s in self.returns.columns]
            if not valid_symbols:
                continue

            sub_rets = self.returns[valid_symbols]
            vols = sub_rets.std() * np.sqrt(252)
            inv_vars = 1.0 / (vols**2 + 1e-9)
            w_ivp = inv_vars / inv_vars.sum()
            mom = sub_rets.mean() * 252

            def norm(s):
                return (s - s.min()) / (s.max() - s.min() + 1e-9) if len(s) > 1 else pd.Series(1.0, index=s.index)

            w_alpha = norm(mom) / (norm(mom).sum() + 1e-9)
            w_hybrid = 0.5 * w_ivp + 0.5 * w_alpha
            w_hybrid = w_hybrid / w_hybrid.sum()

            self.cluster_benchmarks[f"Cluster_{c_id}"] = (sub_rets * w_hybrid).sum(axis=1)
            self.intra_cluster_weights[c_id] = w_hybrid

        core_cluster_weights = self.optimize_across_clusters("risk_parity", cluster_cap=cluster_cap)

        final_alloc = []
        for sym in agg_symbols:
            c_id = symbol_to_cluster.get(sym)
            direction = self.meta.get(str(sym), {}).get("direction", "LONG")
            final_alloc.append(
                {
                    "Symbol": sym,
                    "Description": self.meta.get(str(sym), {}).get("description", "N/A"),
                    "Sector": self.meta.get(str(sym), {}).get("sector", "N/A"),
                    "Cluster_ID": str(c_id),
                    "Cluster_Label": f"Cluster {c_id} (AGGRESSOR)",
                    "Weight": float(agg_weight_per),
                    "Cluster_Weight": float(agg_weight_per),
                    "Type": "AGGRESSOR (Antifragile)",
                    "Direction": direction,
                    "Market": self.meta.get(str(sym), {}).get("market", "UNKNOWN"),
                    "Net_Weight": float(agg_weight_per) * (1.0 if direction == "LONG" else -1.0),
                }
            )

        for c_col, c_weight in core_cluster_weights.items():
            if c_weight < 1e-6:
                continue
            c_id = str(c_col).replace("Cluster_", "")
            intra_w = self.intra_cluster_weights[c_id]
            for sym, sym_w_in_cluster in intra_w.items():
                if sym_w_in_cluster * c_weight < 1e-6:
                    continue
                direction = self.meta.get(str(sym), {}).get("direction", "LONG")
                final_alloc.append(
                    {
                        "Symbol": sym,
                        "Description": self.meta.get(str(sym), {}).get("description", "N/A"),
                        "Sector": self.meta.get(str(sym), {}).get("sector", "N/A"),
                        "Cluster_ID": c_id,
                        "Cluster_Label": f"Cluster {c_id}",
                        "Weight": float(c_weight * sym_w_in_cluster * 0.90),
                        "Cluster_Weight": float(c_weight * 0.90),
                        "Type": "CORE (Safe)",
                        "Direction": direction,
                        "Market": self.meta.get(str(sym), {}).get("market", "UNKNOWN"),
                        "Net_Weight": float(c_weight * sym_w_in_cluster * 0.90) * (1.0 if direction == "LONG" else -1.0),
                    }
                )

        self.returns = original_returns  # Restore
        df = pd.DataFrame(final_alloc).sort_values("Weight", ascending=False)
        if top_n > 0:
            df = df.head(top_n)
        return df

    def get_cluster_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        summary = []
        for c_id, group in df.groupby("Cluster_ID"):
            lead_asset = group.sort_values("Weight", ascending=False).iloc[0]
            sector_counts = group["Sector"].value_counts()
            primary_sector = str(sector_counts.index[0]) if not sector_counts.empty else "N/A"

            summary.append(
                {
                    "Cluster_ID": str(c_id),
                    "Cluster_Label": lead_asset["Cluster_Label"],
                    "Gross_Weight": float(group["Weight"].sum()),
                    "Net_Weight": float(group["Net_Weight"].sum()),
                    "Asset_Count": int(len(group)),
                    "Lead_Asset": lead_asset["Symbol"],
                    "Lead_Description": lead_asset["Description"],
                    "Sectors": primary_sector,
                    "Markets": list(group["Market"].unique()),
                    "Type": group["Type"].iloc[0] if "Type" in group.columns else "CORE",
                }
            )
        return pd.DataFrame(summary).sort_values("Gross_Weight", ascending=False)


def main():
    from tradingview_scraper.regime import MarketRegimeDetector

    opt = ClusteredOptimizerV2(
        returns_path="data/lakehouse/portfolio_returns.pkl",
        clusters_path="data/lakehouse/portfolio_clusters.json",
        meta_path="data/lakehouse/portfolio_meta.json",
        stats_path="data/lakehouse/antifragility_stats.json",
    )

    # Detect Regime for audit
    detector = MarketRegimeDetector()
    returns_df = cast(pd.DataFrame, opt.returns)
    regime_name, regime_score = detector.detect_regime(returns_df)

    cluster_cap = float(os.getenv("CLUSTER_CAP", "0.25"))
    top_n = int(os.getenv("TOP_N_ASSETS", "0"))

    profiles_raw = {
        "min_variance": opt.run_profile("Min Variance", "min_var", cluster_cap=cluster_cap, top_n=top_n),
        "risk_parity": opt.run_profile("Risk Parity", "risk_parity", cluster_cap=cluster_cap, top_n=top_n),
        "max_sharpe": opt.run_profile("Max Sharpe", "max_sharpe", cluster_cap=cluster_cap, top_n=top_n),
        "barbell": opt.run_barbell(cluster_cap=cluster_cap, top_n=top_n),
    }

    cluster_registry = {}
    for c_id, symbols in opt.clusters.items():
        valid_symbols = [s for s in symbols if s in opt.returns.columns]
        if not valid_symbols:
            continue
        sectors = [opt.meta.get(s, {}).get("sector", "N/A") for s in valid_symbols]
        sector_counts = pd.Series(sectors).value_counts()
        primary_sector = str(sector_counts.index[0]) if not sector_counts.empty else "N/A"

        cluster_registry[c_id] = {
            "symbols": valid_symbols,
            "size": len(valid_symbols),
            "primary_sector": primary_sector,
            "markets": list(set(opt.meta.get(s, {}).get("market", "UNKNOWN") for s in valid_symbols)),
        }

    # Audit Data Collection (Stage 4)
    if os.path.exists(AUDIT_FILE):
        with open(AUDIT_FILE, "r") as f_audit:
            full_audit = json.load(f_audit)
    else:
        full_audit = {}

    full_audit["optimization"] = {
        "timestamp": str(pd.Timestamp.now()),
        "regime": {"name": regime_name, "score": regime_score},
        "constraints": {"cluster_cap": cluster_cap, "top_n": top_n},
        "profiles": {
            name: {
                "assets": len(df),
                "top_cluster": str(opt.get_cluster_summary(df).iloc[0]["Cluster_ID"]) if not df.empty else "N/A",
                "total_gross": float(df["Weight"].sum()) if not df.empty else 0.0,
                "total_net": float(df["Net_Weight"].sum()) if not df.empty else 0.0,
            }
            for name, df in profiles_raw.items()
        },
    }
    with open(AUDIT_FILE, "w") as f_audit_out:
        json.dump(full_audit, f_audit_out, indent=2)

    output = {"profiles": {}, "cluster_registry": cluster_registry}
    for name, df in profiles_raw.items():
        cluster_sum = opt.get_cluster_summary(df)
        output["profiles"][name] = {"assets": df.to_dict(orient="records"), "clusters": cluster_sum.to_dict(orient="records")}
        print(f"\n--- {name.upper()} PROFILE ---\nTOP ASSETS:\n{df.head(10).to_string(index=False)}\nCLUSTER SUMMARY:\n{cluster_sum.to_string(index=False)}")

    with open("data/lakehouse/portfolio_optimized_v2.json", "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Saved all profiles and cluster details to data/lakehouse/portfolio_optimized_v2.json")
    logger.info(f"Audit log updated: {AUDIT_FILE}")


if __name__ == "__main__":
    main()
