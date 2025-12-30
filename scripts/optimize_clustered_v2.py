import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast

import cvxpy as cp
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from tradingview_scraper.utils.scoring import calculate_liquidity_score, normalize_series

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

        if not available_symbols:
            logger.warning("No available symbols for optimization.")
            self.returns = pd.DataFrame()
        else:
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

            # --- Execution Alpha Calculation ---
            mom = sub_rets.mean() * 252
            vols = sub_rets.std() * np.sqrt(252)
            stab = 1.0 / (vols + 1e-9)

            # Convexity
            conv = pd.Series(0.0, index=valid_symbols)
            if self.stats is not None:
                common = [s for s in valid_symbols if s in self.stats["Symbol"].values]
                if common:
                    conv.loc[common] = self.stats.set_index("Symbol").loc[common, "Antifragility_Score"]

            # Liquidity Score (Value Traded + Spread Proxy)
            liq = pd.Series({s: calculate_liquidity_score(s, self.meta) for s in valid_symbols})

            # Combined Alpha execution score
            alpha_exec = 0.3 * normalize_series(mom) + 0.2 * normalize_series(stab) + 0.2 * normalize_series(conv) + 0.3 * normalize_series(liq)
            w_alpha = alpha_exec / (alpha_exec.sum() + 1e-9)

            # 1. Hybrid Layer 2 Weighting (Blend of InvVar and AlphaRank)
            inv_vars = 1.0 / (vols**2 + 1e-9)
            w_ivp = inv_vars / inv_vars.sum()

            # 50/50 Blend
            w_hybrid = 0.5 * w_ivp + 0.5 * w_alpha
            w_hybrid = w_hybrid / w_hybrid.sum()

            self.cluster_benchmarks[f"Cluster_{c_id}"] = (sub_rets * w_hybrid).sum(axis=1)
            self.intra_cluster_weights[c_id] = w_hybrid

            # 2. Aggregate cluster fragility (CVaR)
            if self.stats is not None:
                c_af_stats = self.stats[self.stats["Symbol"].isin(valid_symbols)]
                if not c_af_stats.empty:
                    if "Fragility_Score" in c_af_stats.columns:
                        fragility = float(np.mean(c_af_stats["Fragility_Score"]))
                    else:
                        antif = c_af_stats["Antifragility_Score"] if "Antifragility_Score" in c_af_stats.columns else pd.Series(0.0, index=c_af_stats.index)
                        anti_norm = antif / (float(antif.max()) + 1e-9)

                        if "CVaR_95" in c_af_stats.columns:
                            tail = np.abs(c_af_stats["CVaR_95"])
                        elif "Vol" in c_af_stats.columns:
                            tail = c_af_stats["Vol"]
                        else:
                            tail = pd.Series(0.0, index=c_af_stats.index)

                        tail_norm = tail / (float(np.max(tail)) + 1e-9) if len(tail) else tail
                        fragility = float(np.mean((1.0 - anti_norm) + tail_norm))

                    if "CVaR_95" in c_af_stats.columns:
                        cvar_value = float(np.mean(c_af_stats["CVaR_95"]))
                    elif "Vol" in c_af_stats.columns:
                        cvar_value = float(np.mean(c_af_stats["Vol"]))
                    else:
                        cvar_value = -0.05

                    self.cluster_stats[c_id] = {"fragility": fragility, "cvar": cvar_value}
                else:
                    self.cluster_stats[c_id] = {"fragility": 1.0, "cvar": -0.05}
            else:
                self.cluster_stats[c_id] = {"fragility": 1.0, "cvar": -0.05}

    def _get_cov(self, df: pd.DataFrame) -> np.ndarray:
        return df.cov().values * 252

    def optimize_across_clusters(self, method: str, cluster_cap: float = 0.25) -> pd.Series:
        if self.cluster_benchmarks.empty:
            return pd.Series(dtype=float)

        n = self.cluster_benchmarks.shape[1]
        if n == 1:
            return pd.Series([1.0], index=self.cluster_benchmarks.columns)

        # Optimization Parameters
        cov = self._get_cov(self.cluster_benchmarks)
        mu = self.cluster_benchmarks.mean().values * 252
        penalties = np.array([self.cluster_stats[c_col.replace("Cluster_", "")]["fragility"] for c_col in self.cluster_benchmarks.columns])

        # CVXPY Setup
        w = cp.Variable(n)
        risk = cp.quad_form(w, cov)
        p_term = (w @ penalties) * 0.2

        constraints = [cp.sum(w) == 1.0, w >= 0.0, w <= cluster_cap]

        if method == "min_var":
            obj = cp.Minimize(risk + p_term)
        elif method == "risk_parity":
            # Log-barrier RP approximation
            obj = cp.Minimize(0.5 * risk - (1.0 / n) * cp.sum(cp.log(w)))
        elif method == "max_sharpe":
            # Quadratic Utility
            obj = cp.Maximize((mu @ w) - 0.5 * risk - p_term)
        else:
            raise ValueError(f"Unknown method {method}")

        try:
            prob = cp.Problem(obj, constraints)
            prob.solve(solver=cp.ECOS if method == "risk_parity" else cp.OSQP)

            if w.value is None or prob.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
                logger.warning(f"Solver {method} failed (Status: {prob.status}), falling back to SLSQP")
                # Fallback to SLSQP if CVXPY fails
                return self._optimize_slsqp(method, cluster_cap, n, cov, penalties, mu)

            return pd.Series(np.array(w.value).flatten(), index=self.cluster_benchmarks.columns)
        except Exception as e:
            logger.error(f"CVXPY error: {e}, falling back to SLSQP")
            return self._optimize_slsqp(method, cluster_cap, n, cov, penalties, mu)

    def _optimize_slsqp(self, method: str, cluster_cap: float, n: int, cov: np.ndarray, penalties: np.ndarray, mu: np.ndarray) -> pd.Series:
        """Legacy SLSQP fallback for robustness."""
        init_weights = np.array([1.0 / n] * n)
        bounds = tuple((0.0, cluster_cap) for _ in range(n))
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        def min_var_obj(w, c, p):
            vol = np.sqrt(np.dot(w.T, np.dot(c, w)))
            penalty = np.dot(w, p)
            return vol * (1.0 + penalty * 0.2)

        def risk_parity_obj(w, c):
            vol = np.sqrt(np.dot(w.T, np.dot(c, w)))
            if vol == 0:
                return 0
            mrc = np.dot(c, w) / vol
            rc = w * mrc
            return np.sum(np.square(rc - vol / len(w)))

        def max_sharpe_obj(w, m, c, p):
            vol = np.sqrt(np.dot(w.T, np.dot(c, w)))
            ret = np.sum(m * w)
            if vol == 0:
                return 0
            sharpe = ret / vol
            penalty = np.dot(w, p)
            return -(sharpe / (1.0 + penalty * 0.2))

        if method == "min_var":
            res = minimize(min_var_obj, init_weights, args=(cov, penalties), method="SLSQP", bounds=bounds, constraints=constraints)
        elif method == "risk_parity":
            res = minimize(risk_parity_obj, init_weights, args=(cov,), method="SLSQP", bounds=bounds, constraints=constraints)
        elif method == "max_sharpe":
            res = minimize(max_sharpe_obj, init_weights, args=(mu, cov, penalties), method="SLSQP", bounds=bounds, constraints=constraints)
        else:
            return pd.Series(init_weights, index=self.cluster_benchmarks.columns)

        return pd.Series(res.x, index=self.cluster_benchmarks.columns)

    def calculate_portfolio_beta(self, weights_df: pd.DataFrame, benchmark_symbol: str = "AMEX:SPY") -> float:
        if weights_df.empty:
            return 0.0

        # Load benchmark history
        from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

        loader = PersistentDataLoader()

        # Determine date range from returns
        end_date = str(self.returns.index[-1])
        start_date = str(self.returns.index[0])

        try:
            bench_df = loader.load(benchmark_symbol, start_date, end_date, interval="1d")
            if bench_df.empty:
                logger.warning(f"Benchmark {benchmark_symbol} history empty.")
                return 0.0

            bench_df["timestamp"] = pd.to_datetime(bench_df["timestamp"], unit="s").dt.date
            bench_rets = bench_df.set_index("timestamp")["close"].pct_change().dropna()

            # Align with returns (normalize indices to avoid date-vs-timestamp mismatches)
            returns_aligned = self.returns.copy()
            returns_aligned.index = pd.to_datetime(returns_aligned.index)
            bench_rets.index = pd.to_datetime(bench_rets.index)

            common_idx = returns_aligned.index.intersection(bench_rets.index)
            if len(common_idx) < 20:
                logger.warning(f"Insufficient common dates for beta: {len(common_idx)}")
                return 0.0

            weight_col = "Net_Weight" if "Net_Weight" in weights_df.columns else "Weight"
            weights = weights_df.set_index("Symbol")[weight_col].astype(float)
            weights = weights.reindex(returns_aligned.columns).fillna(0.0)

            port_rets = returns_aligned.loc[common_idx].dot(weights)
            bench_rets = bench_rets.loc[common_idx]

            # Calculate Beta
            cov = np.cov(port_rets, bench_rets)[0, 1]
            var = np.var(bench_rets)
            return float(cov / (var + 1e-9))
        except Exception as e:
            logger.error(f"Failed to calculate beta: {e}")
            return 0.0

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

            # --- Execution Alpha Calculation ---
            mom = sub_rets.mean() * 252
            vols = sub_rets.std() * np.sqrt(252)
            stab = 1.0 / (vols + 1e-9)
            conv = pd.Series(0.0, index=valid_symbols)
            common = [s for s in valid_symbols if s in self.stats["Symbol"].values]
            if common:
                conv.loc[common] = self.stats.set_index("Symbol").loc[common, "Antifragility_Score"]
            liq = pd.Series({s: calculate_liquidity_score(s, self.meta) for s in valid_symbols})

            alpha_exec = 0.3 * normalize_series(mom) + 0.2 * normalize_series(stab) + 0.2 * normalize_series(conv) + 0.3 * normalize_series(liq)
            w_alpha = alpha_exec / (alpha_exec.sum() + 1e-9)

            w_ivp = (1.0 / (vols**2 + 1e-9)) / (1.0 / (vols**2 + 1e-9)).sum()
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

    output = {
        "profiles": {},
        "cluster_registry": cluster_registry,
        "optimization": {
            "timestamp": str(pd.Timestamp.now()),
            "regime": {"name": regime_name, "score": regime_score},
            "constraints": {"cluster_cap": cluster_cap, "top_n": top_n},
        },
    }

    profile_beta: Dict[str, float] = {}
    for name, df in profiles_raw.items():
        cluster_sum = opt.get_cluster_summary(df)
        beta_spy = opt.calculate_portfolio_beta(df, "AMEX:SPY")
        profile_beta[name] = beta_spy

        output["profiles"][name] = {
            "assets": df.to_dict(orient="records"),
            "clusters": cluster_sum.to_dict(orient="records"),
            "beta_spy": beta_spy,
        }

        print(f"\n--- {name.upper()} PROFILE ---")
        print(f"BETA TO SPY: {beta_spy:.4f}")
        print(f"TOP ASSETS:\n{df.head(10).to_string(index=False)}")
        print(f"CLUSTER SUMMARY:\n{cluster_sum.to_string(index=False)}")

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
                "beta_spy": profile_beta.get(name, 0.0),
            }
            for name, df in profiles_raw.items()
        },
    }

    with open(AUDIT_FILE, "w") as f_audit_out:
        json.dump(full_audit, f_audit_out, indent=2)

    with open("data/lakehouse/portfolio_optimized_v2.json", "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Saved all profiles and cluster details to data/lakehouse/portfolio_optimized_v2.json")
    logger.info(f"Audit log updated: {AUDIT_FILE}")


if __name__ == "__main__":
    main()
