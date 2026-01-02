import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import cvxpy as cp
import numpy as np
import pandas as pd

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash  # type: ignore
from tradingview_scraper.utils.scoring import calculate_liquidity_score, normalize_series

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("clustered_optimizer_v2")

AUDIT_FILE = "data/lakehouse/selection_audit.json"


class ClusteredOptimizerV2:
    def __init__(self, returns_path: str, clusters_path: str, meta_path: str, stats_path: Optional[str] = None):
        self.settings = get_settings()
        self.run_dir = self.settings.prepare_summaries_run_dir()
        self.ledger = None
        if self.settings.features.feat_audit_ledger:
            self.ledger = AuditLedger(self.run_dir)

        # Explicitly cast to DataFrame to satisfy linter
        with open(returns_path, "rb") as f_in:
            df = cast(pd.DataFrame, pd.read_pickle(f_in))
            # Ultra-robust forcing of naive index
            try:
                new_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in df.index]
                df.index = pd.DatetimeIndex(new_idx)
            except Exception as e_idx:
                logger.warning(f"Fallback indexing for returns: {e_idx}")
                df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
            self.returns = df

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
        self.last_aggressor_ids = []

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

    def run_profile(self, profile: str, method: str, cluster_cap: float = 0.25, prev_weights: Optional[pd.Series] = None) -> pd.DataFrame:
        """Entry point for standard risk profiles."""
        if self.ledger:
            self.ledger.record_intent(step=f"optimize_{profile}", params={"method": method, "cap": cluster_cap}, input_hashes={"returns": get_df_hash(self.returns)})
        cluster_weights = self.optimize_across_clusters(method, cluster_cap, prev_weights)
        weights_df = self._build_final_weights(cluster_weights)
        if self.ledger:
            self.ledger.record_outcome(step=f"optimize_{profile}", status="success", output_hashes={"weights": get_df_hash(weights_df)}, metrics={"n_assets": len(weights_df)})
        return weights_df

    def run_barbell(self, cluster_cap: float = 0.25, regime: str = "NORMAL") -> pd.DataFrame:
        """Entry point for the Antifragile Barbell profile."""
        if self.stats is None:
            return pd.DataFrame()

        best_per_cluster = {}
        for c_id, symbols in self.clusters.items():
            valid = [s for s in symbols if s in self.returns.columns]
            if not valid:
                continue
            common = [s for s in valid if s in self.stats["Symbol"].values]
            if common:
                best_per_cluster[c_id] = self.stats.set_index("Symbol").loc[common, "Antifragility_Score"].max()

        sorted_clusters = sorted(best_per_cluster.items(), key=lambda x: x[1], reverse=True)
        aggressor_ids = [c[0] for c in sorted_clusters[:2]]

        # Dynamic Regime Scaling
        settings = get_settings()
        if settings.features.feat_spectral_regimes:
            # Map standard Barbell REGIME_SPLITS
            agg_weight = {"QUIET": 0.15, "NORMAL": 0.10, "TURBULENT": 0.05, "CRISIS": 0.03}.get(regime, 0.10)
        else:
            agg_weight = 0.30

        core_weight = 1.0 - agg_weight

        core_c_ids = [c for c in self.clusters.keys() if c not in aggressor_ids]
        core_cols = [f"Cluster_{c}" for c in core_c_ids if f"Cluster_{c}" in self.cluster_benchmarks.columns]
        agg_cols = [f"Cluster_{c}" for c in aggressor_ids if f"Cluster_{c}" in self.cluster_benchmarks.columns]

        if not core_cols:
            # Fallback to simple optimization if core is empty
            return self.run_profile("risk_parity", "risk_parity", cluster_cap)

        # 1. Optimize Core Sleeve (Risk Parity)
        w_core = self._solve_cvxpy_direct(cast(pd.DataFrame, self.cluster_benchmarks[core_cols]), "risk_parity", cluster_cap)
        w_core_series = pd.Series(w_core * core_weight, index=core_cols)

        # 2. Optimize Aggressor Sleeve (Max Sharpe or high-alpha objective)
        # Note: Aggressor sleeve has no cluster_cap constraint to allow concentration in the 'best' buckets
        w_agg = self._solve_cvxpy_direct(cast(pd.DataFrame, self.cluster_benchmarks[agg_cols]), "max_sharpe", 1.0)
        w_agg_series = pd.Series(w_agg * agg_weight, index=agg_cols)

        # Combined Cluster Weights
        cluster_weights = pd.concat([w_core_series, w_agg_series])

        # Force unique symbol per aggressor cluster for the Aggressor sleeve
        # but allow Core to remain diversified.
        aggressor_symbols = []
        for c_id in aggressor_ids:
            symbols = self.clusters[c_id]
            valid = [s for s in symbols if s in self.returns.columns]
            if not valid:
                continue
            common = [s for s in valid if s in self.stats["Symbol"].values]
            if common:
                lead = self.stats.set_index("Symbol").loc[common, "Antifragility_Score"].idxmax()
                aggressor_symbols.append(lead)

        # Build final rows
        rows = []
        # Add Core assets (Normal intra-cluster weighting)
        for c_col, c_w in w_core_series.items():
            if float(c_w) < 1e-6:
                continue
            c_id = str(c_col).replace("Cluster_", "")
            intra_w = self.intra_cluster_weights[c_id]
            for sym, s_w in intra_w.items():
                final_w = c_w * s_w
                if final_w < 1e-6:
                    continue
                m = self.meta.get(sym, {})
                direction = m.get("direction", "LONG")
                rows.append(
                    {
                        "Symbol": sym,
                        "Weight": final_w,
                        "Net_Weight": final_w * (1.0 if direction == "LONG" else -1.0),
                        "Direction": direction,
                        "Cluster_ID": c_id,
                        "Type": "CORE",
                        "Description": m.get("description", "N/A"),
                        "Sector": m.get("sector", "N/A"),
                        "Market": m.get("market", "UNKNOWN"),
                    }
                )

        # Add Aggressor assets (Lead only, using its sleeve optimization weight)
        for c_col, c_w in w_agg_series.items():
            if float(c_w) < 1e-6:
                continue
            c_id = str(c_col).replace("Cluster_", "")
            # Find lead asset for this cluster
            symbols = self.clusters[c_id]
            valid = [s for s in symbols if s in self.returns.columns]
            common = [s for s in valid if s in self.stats["Symbol"].values]
            if common:
                lead = self.stats.set_index("Symbol").loc[common, "Antifragility_Score"].idxmax()
                m = self.meta.get(lead, {})
                direction = m.get("direction", "LONG")
                rows.append(
                    {
                        "Symbol": lead,
                        "Weight": float(c_w),
                        "Net_Weight": float(c_w) * (1.0 if direction == "LONG" else -1.0),
                        "Direction": direction,
                        "Cluster_ID": c_id,
                        "Type": "AGGRESSOR",
                        "Description": m.get("description", "N/A"),
                        "Sector": m.get("sector", "N/A"),
                        "Market": m.get("market", "UNKNOWN"),
                    }
                )

        self.last_aggressor_ids = [str(c) for c in aggressor_ids]
        return pd.DataFrame(rows).sort_values("Weight", ascending=False)

        self.last_aggressor_ids = [str(c) for c in aggressor_ids]
        return pd.DataFrame(rows).sort_values("Weight", ascending=False)

    def optimize_across_clusters(self, method: str, cluster_cap: float = 0.25, prev_weights: Optional[pd.Series] = None) -> pd.Series:
        if self.cluster_benchmarks.empty:
            return pd.Series(dtype=float)

        n = self.cluster_benchmarks.shape[1]
        if n == 1:
            return pd.Series([1.0], index=self.cluster_benchmarks.columns)

        w = self._solve_cvxpy_direct(self.cluster_benchmarks, method, cluster_cap, prev_weights)
        return pd.Series(w, index=self.cluster_benchmarks.columns)

    def _solve_cvxpy_direct(self, benchmarks: pd.DataFrame, method: str, cluster_cap: float, prev_weights: Optional[pd.Series] = None) -> np.ndarray:
        n = benchmarks.shape[1]
        cov = self._get_cov(benchmarks)
        mu = np.asarray(benchmarks.mean(), dtype=float) * 252

        # Safe lookup for penalties
        penalty_list = []
        for c_col in benchmarks.columns:
            c_id = str(c_col).replace("Cluster_", "")
            frag = self.cluster_stats.get(c_id, {}).get("fragility", 1.0)
            penalty_list.append(frag)
        penalties = np.array(penalty_list)

        w = cp.Variable(n)
        risk = cp.quad_form(w, cov)
        p_term = (w @ penalties) * 0.2

        # Turnover penalty (L1 norm of change from previous cluster weights)
        t_penalty = 0.0
        if prev_weights is not None and not prev_weights.empty:
            # Map asset weights to cluster weights
            # This is complex because we are optimizing clusters here.
            # We approximate by looking at previous weights per cluster column.
            # (In our framework, cluster weights are stable units)
            pass

        constraints = [cp.sum(w) == 1.0, w >= 0.0, w <= cluster_cap]

        if method in {"min_var", "min_variance"}:
            obj = cp.Minimize(risk + p_term)
        elif method in {"risk_parity", "hrp"}:
            obj = cp.Minimize(0.5 * risk - (1.0 / n) * cp.sum(cp.log(w)))
        elif method == "max_sharpe":
            obj = cp.Maximize((mu @ w) - 0.5 * risk - p_term - 0.001 * cp.norm(w, 1))
        else:
            obj = cp.Minimize(risk)

        try:
            prob = cp.Problem(obj, constraints)
            prob.solve(solver=cp.ECOS if "risk_parity" in method or "hrp" in method else cp.OSQP)
            if w.value is None:
                return np.array([1.0 / n] * n)
            return np.array(w.value).flatten()
        except Exception:
            return np.array([1.0 / n] * n)

    def _build_final_weights(self, cluster_weights: pd.Series) -> pd.DataFrame:
        rows = []
        for c_col, c_w in cluster_weights.items():
            if float(c_w) < 1e-6:
                continue
            c_id = str(c_col).replace("Cluster_", "")
            intra_w = self.intra_cluster_weights[c_id]

            for sym, s_w in intra_w.items():
                final_w = c_w * s_w
                if final_w < 1e-6:
                    continue
                m = self.meta.get(sym, {})
                direction = m.get("direction", "LONG")
                rows.append(
                    {
                        "Symbol": sym,
                        "Weight": final_w,
                        "Net_Weight": final_w * (1.0 if direction == "LONG" else -1.0),
                        "Direction": direction,
                        "Cluster_ID": c_id,
                        "Description": m.get("description", "N/A"),
                        "Sector": m.get("sector", "N/A"),
                        "Market": m.get("market", "UNKNOWN"),
                    }
                )
        return pd.DataFrame(rows).sort_values("Weight", ascending=False)


if __name__ == "__main__":
    from tradingview_scraper.regime import MarketRegimeDetector

    optimizer = ClusteredOptimizerV2(
        returns_path="data/lakehouse/portfolio_returns.pkl",
        clusters_path="data/lakehouse/portfolio_clusters.json",
        meta_path="data/lakehouse/portfolio_meta.json",
        stats_path="data/lakehouse/antifragility_stats.json",
    )

    detector = MarketRegimeDetector()
    regime, score = detector.detect_regime(optimizer.returns)
    logger.info(f"Regime Detected for Optimization: {regime} (Score: {score:.2f})")

    cap = float(os.getenv("CLUSTER_CAP", "0.25"))

    # Generate results for each profile
    profiles = {}
    for p_name, method in [
        ("min_variance", "min_variance"),
        ("hrp", "hrp"),
        ("max_sharpe", "max_sharpe"),
        ("equal_weight", "equal_weight"),
    ]:
        logger.info(f"Optimizing profile: {p_name}")
        weights_df = optimizer.run_profile(p_name, method, cap)

        # Build cluster summary for this profile
        cluster_summary = []
        for c_id in optimizer.clusters.keys():
            sub = weights_df[weights_df["Cluster_ID"] == str(c_id)]
            if sub.empty:
                continue
            gross = sub["Weight"].sum()
            net = sub["Net_Weight"].sum()
            cluster_summary.append(
                {
                    "Cluster_Label": f"Cluster {c_id}",
                    "Gross_Weight": float(gross),
                    "Net_Weight": float(net),
                    "Lead_Asset": sub.iloc[0]["Symbol"],
                    "Asset_Count": len(sub),
                    "Type": "CORE",  # Placeholder
                    "Sectors": list(sub["Sector"].unique()),
                }
            )

        profiles[p_name] = {
            "assets": weights_df.to_dict(orient="records"),
            "clusters": cluster_summary,
        }

    # Add Antifragile Barbell
    logger.info("Optimizing profile: barbell")
    barbell_df = optimizer.run_barbell(cap, regime)
    if not barbell_df.empty:
        barbell_summary = []
        for c_id in optimizer.clusters.keys():
            sub = barbell_df[barbell_df["Cluster_ID"] == str(c_id)]
            if sub.empty:
                continue
            gross = sub["Weight"].sum()
            net = sub["Net_Weight"].sum()
            barbell_summary.append(
                {
                    "Cluster_Label": f"Cluster {c_id}",
                    "Gross_Weight": float(gross),
                    "Net_Weight": float(net),
                    "Lead_Asset": sub.iloc[0]["Symbol"],
                    "Asset_Count": len(sub),
                    "Type": sub.iloc[0]["Type"],
                    "Sectors": list(sub["Sector"].unique()),
                }
            )
        profiles["barbell"] = {
            "assets": barbell_df.to_dict(orient="records"),
            "clusters": barbell_summary,
        }

    # Build cluster registry
    registry = {}
    for c_id, symbols in optimizer.clusters.items():
        # Find primary sector from meta
        sectors = [optimizer.meta.get(s, {}).get("sector", "N/A") for s in symbols]
        primary = max(set(sectors), key=sectors.count) if sectors else "N/A"
        registry[c_id] = {"symbols": symbols, "primary_sector": primary}

    output = {
        "profiles": profiles,
        "cluster_registry": registry,
        "optimization": {"regime": {"name": regime, "score": float(score)}},
        "metadata": {"generated_at": datetime.now().isoformat(), "cluster_cap": cap},
    }

    output_path = "data/lakehouse/portfolio_optimized_v2.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"✅ Clustered Optimization V2 Complete. Saved to: {output_path}")
