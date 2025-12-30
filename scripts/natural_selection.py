import json
import logging
import os
from typing import Any, Dict, List, cast

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform

from tradingview_scraper.utils.scoring import calculate_liquidity_score, normalize_series

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("natural_selection")

AUDIT_FILE = "data/lakehouse/selection_audit.json"


def get_robust_correlation(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a robust correlation matrix using intersection of active trading days
    to avoid dilution from padding (e.g. TradFi weekends vs Crypto 24/7).
    """
    if returns.empty:
        return pd.DataFrame()

    # Vectorized correlation with min_periods requirement
    # This handles active trading day intersections efficiently
    corr = returns.replace(0, np.nan).corr(min_periods=20)
    return corr.fillna(0.0)


def natural_selection(
    returns_path: str = "data/lakehouse/portfolio_returns.pkl",
    meta_path: str = "data/lakehouse/portfolio_candidates_raw.json",
    stats_path: str = "data/lakehouse/antifragility_stats.json",
    output_path: str = "data/lakehouse/portfolio_candidates.json",
    top_n_per_cluster: int = 3,  # Target Top 3 per direction
    dist_threshold: float = 0.4,
    max_clusters: int = 25,
):
    if not os.path.exists(returns_path) or not os.path.exists(meta_path):
        logger.error("Returns matrix or raw candidates file missing.")
        return

    # 1. Load Data
    with open(returns_path, "rb") as f_in:
        returns_raw = pd.read_pickle(f_in)

    if not isinstance(returns_raw, pd.DataFrame):
        returns = pd.DataFrame(returns_raw)
    else:
        returns = returns_raw

    with open(meta_path, "r") as f_meta:
        raw_candidates = json.load(f_meta)

    candidate_map = {c["symbol"]: c for c in raw_candidates}

    stats_df = None
    if os.path.exists(stats_path):
        stats_df = pd.read_json(stats_path).set_index("Symbol")

    # Audit Data Collection with explicit typing
    audit_selection: Dict[str, Any] = {"total_raw_symbols": len(returns.columns), "lookbacks_used": [], "clusters": {}, "total_selected": 0}

    # 2. Multi-Lookback Persistent Clustering
    lookbacks = [60, 120, 200]
    available_len = len(returns)
    valid_lookbacks = [l for l in lookbacks if l <= available_len]

    if not valid_lookbacks:
        valid_lookbacks = [available_len]

    audit_selection["lookbacks_used"] = valid_lookbacks

    logger.info(f"Natural Selection using multi-lookback: {valid_lookbacks}")

    dist_matrices = []
    for l in valid_lookbacks:
        rets_subset = returns.tail(l)
        corr = get_robust_correlation(rets_subset)
        dist = np.sqrt(0.5 * (1 - corr.values.clip(-1, 1)))
        dist_matrices.append(dist)

    avg_dist_matrix = np.mean(dist_matrices, axis=0)
    avg_dist_matrix = (avg_dist_matrix + avg_dist_matrix.T) / 2
    np.fill_diagonal(avg_dist_matrix, 0)

    condensed = squareform(avg_dist_matrix, checks=False)
    link = sch.linkage(condensed, method="ward")

    # Use distance-based threshold if provided, otherwise maxclust fallback
    if dist_threshold > 0:
        cluster_ids = sch.fcluster(link, t=dist_threshold, criterion="distance")
    else:
        cluster_ids = sch.fcluster(link, t=max_clusters, criterion="maxclust")

    clusters: Dict[int, List[str]] = {}
    for sym, c_id in zip(returns.columns, cluster_ids):
        c_id_int = int(c_id)
        if c_id_int not in clusters:
            clusters[c_id_int] = []
        clusters[c_id_int].append(str(sym))

    logger.info(f"Natural Selection: Identified {len(clusters)} risk clusters from {len(returns.columns)} symbols (Target={max_clusters}).")

    # 3. Selection within Clusters: Top LONG and Top SHORT
    selected_symbols = []
    for c_id, symbols in clusters.items():
        # Alpha Ranking
        sub_rets = returns[symbols]
        mom = sub_rets.mean() * 252
        vol = sub_rets.std() * np.sqrt(252)
        stab = 1.0 / (vol + 1e-9)

        conv = pd.Series(0.0, index=symbols)
        if stats_df is not None:
            common = [s for s in symbols if s in stats_df.index]
            if common:
                conv.loc[common] = stats_df.loc[common, "Antifragility_Score"]

        # Liquidity Score (Value Traded + Spread Proxy)
        liq = pd.Series({s: calculate_liquidity_score(s, candidate_map) for s in symbols})

        # Map symbols to identities and directions
        sym_to_ident = {s: candidate_map.get(s, {}).get("identity", s) for s in symbols}
        directions = pd.Series({s: candidate_map.get(s, {}).get("direction", "LONG") for s in symbols})

        alpha_scores = 0.3 * normalize_series(mom) + 0.2 * normalize_series(stab) + 0.2 * normalize_series(conv) + 0.3 * normalize_series(liq)

        # Audit cluster info
        audit_selection["clusters"][str(c_id)] = {"size": len(symbols), "members": symbols, "selected": []}

        # --- REFINEMENT: Identity-based merging within cluster ---
        # For each identity in this cluster, find the best symbol (venue)
        identity_to_best_sym: Dict[str, str] = {}
        for s in symbols:
            ident = sym_to_ident[s]
            if ident not in identity_to_best_sym or alpha_scores[s] > alpha_scores[identity_to_best_sym[ident]]:
                identity_to_best_sym[ident] = s

        # Best symbols are the unique candidates for this cluster
        unique_cluster_candidates = list(identity_to_best_sym.values())

        # Pick Top N LONGs from unique identities
        long_syms = [s for s in unique_cluster_candidates if directions[s] == "LONG"]
        if long_syms:
            top_longs = alpha_scores[long_syms].sort_values(ascending=False).head(top_n_per_cluster).index.tolist()
            selected_symbols.extend([str(s) for s in top_longs])
            audit_selection["clusters"][str(c_id)]["selected"].extend([str(s) for s in top_longs])

        # Pick Top N SHORTS from unique identities
        short_syms = [s for s in unique_cluster_candidates if directions[s] == "SHORT"]
        if short_syms:
            top_shorts = alpha_scores[short_syms].sort_values(ascending=False).head(top_n_per_cluster).index.tolist()
            selected_symbols.extend([str(s) for s in top_shorts])
            audit_selection["clusters"][str(c_id)]["selected"].extend([str(s) for s in top_shorts])

        n_sel = len([s for s in selected_symbols if s in symbols])
        logger.info(f"  Cluster {c_id}: Selected {n_sel}/{len(symbols)} (L: {len(long_syms)}, S: {len(short_syms)}) [Merged {len(symbols) - len(unique_cluster_candidates)} redundant venues]")

    # 4. Save Final Candidates
    final_candidates = []
    for sym in selected_symbols:
        if sym in candidate_map:
            # Metadata propagation: implementation_alternatives
            final_candidates.append(candidate_map[sym])
        else:
            final_candidates.append({"symbol": sym, "direction": "LONG", "market": "UNKNOWN"})

    audit_selection["total_selected"] = len(final_candidates)

    with open(output_path, "w") as f_out:
        json.dump(final_candidates, f_out, indent=2)

    # Update Audit Log
    full_audit: Dict[str, Any] = {}
    if os.path.exists(AUDIT_FILE):
        with open(AUDIT_FILE, "r") as f_audit:
            full_audit = cast(Dict[str, Any], json.load(f_audit))

    full_audit["selection"] = audit_selection
    with open(AUDIT_FILE, "w") as f_audit_out:
        json.dump(full_audit, f_audit_out, indent=2)

    logger.info(f"Natural Selection Complete: Generated {len(final_candidates)} candidates in {output_path}")
    logger.info(f"Audit log updated: {AUDIT_FILE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=3, help="Number of symbols to pick per direction per cluster")
    parser.add_argument("--threshold", type=float, default=0.4, help="Clustering distance threshold")
    parser.add_argument("--max-clusters", type=int, default=25, help="Target maximum number of clusters")
    args = parser.parse_args()

    natural_selection(top_n_per_cluster=args.top_n, dist_threshold=args.threshold, max_clusters=args.max_clusters)
