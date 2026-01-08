import os

import numpy as np
import pandas as pd


def audit_cluster_cohesion():
    run_id = "20260108-research"
    # Use RAW returns for deeper research
    returns_path = "data/lakehouse/portfolio_returns_raw.pkl"

    if not os.path.exists(returns_path):
        print("Required data files not found in lakehouse.")
        return

    returns = pd.read_pickle(returns_path).fillna(0.0)

    # Perform a research clustering (Threshold 0.0 to see all relationships)
    from tradingview_scraper.selection_engines.engines import get_hierarchical_clusters

    cluster_ids, _ = get_hierarchical_clusters(returns, threshold=0.0, max_clusters=15)

    clusters = {}
    for sym, c_id in zip(returns.columns, cluster_ids):
        cid = str(c_id)
        if cid not in clusters:
            clusters[cid] = []
        clusters[cid].append(sym)

    print("--- Research Cluster Cohesion & Lead-Lag Audit ---")

    results = []
    for c_id, symbols in clusters.items():
        if len(symbols) < 2:
            print(f"\nCluster {c_id}: Single asset ({symbols[0]}). Skipping cohesion audit.")
            continue

        print(f"\nCluster {c_id} Audit (Size: {len(symbols)}): {symbols}")

        # 1. Base Correlation Matrix
        c_returns = returns[symbols]
        corr_matrix = c_returns.corr()
        avg_corr = corr_matrix.values[np.triu_indices(len(symbols), k=1)].mean()
        print(f"Average Intra-Cluster Correlation: {avg_corr:.4f}")

        # 2. Lead-Lag Analysis
        # Identify if any asset leads the others by 1 day
        max_lead_corr = -1.0
        best_leader = None
        best_follower = None

        for i in symbols:
            for j in symbols:
                if i == j:
                    continue
                # Correlation of i leading j (i_t-1 vs j_t)
                lead_corr = returns[i].shift(1).corr(returns[j])
                if lead_corr > max_lead_corr:
                    max_lead_corr = lead_corr
                    best_leader = i
                    best_follower = j

        print(f"Factor Leader Candidate: {best_leader} leads {best_follower} (Shifted Corr: {max_lead_corr:.4f})")

        results.append({"Cluster": c_id, "Avg_Corr": avg_corr, "Leader": best_leader, "Follower": best_follower, "Lead_Corr": max_lead_corr})

    # Summary Table
    if results:
        df = pd.DataFrame(results)
        print("\n--- Cohesion Summary ---")
        print(df.to_markdown(index=False))


if __name__ == "__main__":
    audit_cluster_cohesion()
