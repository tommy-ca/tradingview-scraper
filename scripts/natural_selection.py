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
    returns = cast(pd.DataFrame, pd.read_pickle(returns_path))
    with open(meta_path, "r") as f:
        raw_candidates = json.load(f)

    # Map candidates for easy lookup
    candidate_map = {c["symbol"]: c for c in raw_candidates}

    stats_df = None
    if os.path.exists(stats_path):
        stats_df = pd.read_json(stats_path).set_index("Symbol")

    # 2. Hierarchical Clustering
    corr = returns.corr()
    dist_matrix = np.sqrt(0.5 * (1 - corr.values.clip(-1, 1)))
    dist_matrix = (dist_matrix + dist_matrix.T) / 2
    np.fill_diagonal(dist_matrix, 0)

    condensed = squareform(dist_matrix, checks=False)
    link = sch.linkage(condensed, method="average")
    cluster_ids = sch.fcluster(link, t=dist_threshold, criterion="distance")

    clusters: Dict[int, List[str]] = {}
    for sym, c_id in zip(returns.columns, cluster_ids):
        c_id_int = int(c_id)
        if c_id_int not in clusters:
            clusters[c_id_int] = []
        clusters[c_id_int].append(sym)

    logger.info(f"Natural Selection: Identified {len(clusters)} risk clusters from {len(returns.columns)} symbols.")

    # 3. Selection within Clusters
    selected_symbols = []

    for c_id, symbols in clusters.items():
        if len(symbols) == 1:
            selected_symbols.append(symbols[0])
            continue

        sub_rets = returns[symbols]

        # Calculate Alpha Components
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

        # Pick top N
        top_cluster_syms = alpha_scores.sort_values(ascending=False).head(top_n_per_cluster).index.tolist()
        selected_symbols.extend(top_cluster_syms)

        logger.info(f"  Cluster {c_id}: Selected {len(top_cluster_syms)}/{len(symbols)} (Top Alpha: {top_cluster_syms[0]})")

    # 4. Save Final Candidates
    final_candidates = []
    for sym in selected_symbols:
        if sym in candidate_map:
            final_candidates.append(candidate_map[sym])
        else:
            # Create minimal entry if missing
            final_candidates.append({"symbol": sym, "direction": "LONG", "market": "UNKNOWN"})

    with open(output_path, "w") as f:
        json.dump(final_candidates, f, indent=2)

    logger.info(f"Natural Selection Complete: Generated {len(final_candidates)} candidates in {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=2, help="Number of symbols to pick per cluster")
    parser.add_argument("--threshold", type=float, default=0.4, help="Clustering distance threshold")
    args = parser.parse_args()

    natural_selection(top_n_per_cluster=args.top_n, dist_threshold=args.threshold)
