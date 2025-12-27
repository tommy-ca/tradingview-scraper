import json
import logging
import os
from typing import Dict, List, cast

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("natural_selection")


def get_robust_correlation(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a robust correlation matrix using intersection of active trading days
    to avoid dilution from padding (e.g. TradFi weekends vs Crypto 24/7).
    """
    symbols = returns.columns
    n = len(symbols)
    corr_matrix = np.eye(n)

    for i in range(n):
        for j in range(i + 1, n):
            s1 = str(symbols[i])
            s2 = str(symbols[j])

            # Extract pair and drop zeros/NaNs
            v1 = cast(np.ndarray, returns[s1].values)
            v2 = cast(np.ndarray, returns[s2].values)

            mask = np.logical_and(np.logical_and(v1 != 0, v2 != 0), np.logical_and(~np.isnan(v1), ~np.isnan(v2)))

            v1_clean = v1[mask]
            v2_clean = v2[mask]

            if len(v1_clean) < 20:
                c = 0.0
            else:
                c = float(np.corrcoef(v1_clean, v2_clean)[0, 1])
                if np.isnan(c):
                    c = 0.0

            corr_matrix[i, j] = c
            corr_matrix[j, i] = c

    return pd.DataFrame(corr_matrix, index=symbols, columns=symbols)


def natural_selection(
    returns_path: str = "data/lakehouse/portfolio_returns.pkl",
    meta_path: str = "data/lakehouse/portfolio_candidates_raw.json",
    stats_path: str = "data/lakehouse/antifragility_stats.json",
    output_path: str = "data/lakehouse/portfolio_candidates.json",
    top_n_per_cluster: int = 2,
    dist_threshold: float = 0.4,
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

    # 2. Multi-Lookback Persistent Clustering
    lookbacks = [60, 120, 200]
    available_len = len(returns)
    valid_lookbacks = [l for l in lookbacks if l <= available_len]

    if not valid_lookbacks:
        valid_lookbacks = [available_len]

    logger.info(f"Natural Selection using multi-lookback: {valid_lookbacks}")

    dist_matrices = []
    for l in valid_lookbacks:
        rets_subset = returns.tail(l)
        corr = get_robust_correlation(rets_subset)
        # Distance = sqrt(0.5 * (1 - rho))
        dist = np.sqrt(0.5 * (1 - corr.values.clip(-1, 1)))
        dist_matrices.append(dist)

    # Average distance across lookbacks for persistence
    avg_dist_matrix = np.mean(dist_matrices, axis=0)
    # Ensure symmetry and 0 diagonal
    avg_dist_matrix = (avg_dist_matrix + avg_dist_matrix.T) / 2
    np.fill_diagonal(avg_dist_matrix, 0)

    condensed = squareform(avg_dist_matrix, checks=False)
    # Switch to Ward linkage for tighter clusters
    link = sch.linkage(condensed, method="ward")
    cluster_ids = sch.fcluster(link, t=dist_threshold, criterion="distance")

    clusters: Dict[int, List[str]] = {}
    for sym, c_id in zip(returns.columns, cluster_ids):
        c_id_int = int(c_id)
        if c_id_int not in clusters:
            clusters[c_id_int] = []
        clusters[c_id_int].append(str(sym))

    logger.info(f"Natural Selection: Identified {len(clusters)} risk clusters from {len(returns.columns)} symbols.")

    # 3. Selection within Clusters
    selected_symbols = []
    for c_id, symbols in clusters.items():
        if len(symbols) <= top_n_per_cluster:
            selected_symbols.extend(symbols)
            continue

        sub_rets = returns[symbols]
        mom = sub_rets.mean() * 252
        vol = sub_rets.std() * np.sqrt(252)
        stab = 1.0 / (vol + 1e-9)

        conv = pd.Series(0.0, index=symbols)
        if stats_df is not None:
            common = [s for s in symbols if s in stats_df.index]
            if common:
                conv.loc[common] = stats_df.loc[common, "Antifragility_Score"]

        def norm(s):
            return (s - s.min()) / (s.max() - s.min() + 1e-9) if len(s) > 1 else pd.Series(1.0, index=s.index)

        alpha_scores = 0.4 * norm(mom) + 0.3 * norm(stab) + 0.3 * norm(conv)
        top_cluster_syms = alpha_scores.sort_values(ascending=False).head(top_n_per_cluster).index.tolist()
        selected_symbols.extend([str(s) for s in top_cluster_syms])

        logger.info(f"  Cluster {c_id}: Selected {len(top_cluster_syms)}/{len(symbols)} (Top Alpha: {top_cluster_syms[0]})")

    # 4. Save Final Candidates
    final_candidates = []
    for sym in selected_symbols:
        if sym in candidate_map:
            final_candidates.append(candidate_map[sym])
        else:
            final_candidates.append({"symbol": sym, "direction": "LONG", "market": "UNKNOWN"})

    with open(output_path, "w") as f_out:
        json.dump(final_candidates, f_out, indent=2)

    logger.info(f"Natural Selection Complete: Generated {len(final_candidates)} candidates in {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=2, help="Number of symbols to pick per cluster")
    parser.add_argument("--threshold", type=float, default=0.4, help="Clustering distance threshold")
    args = parser.parse_args()

    natural_selection(top_n_per_cluster=args.top_n, dist_threshold=args.threshold)
