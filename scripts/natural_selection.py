import json
import hashlib
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash  # type: ignore
from tradingview_scraper.utils.scoring import calculate_liquidity_score, normalize_series, rank_series

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("natural_selection")

AUDIT_FILE = "data/lakehouse/selection_audit.json"


def get_robust_correlation(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty:
        return pd.DataFrame()
    corr = returns.replace(0, np.nan).corr(min_periods=20)
    return corr.fillna(0.0)


def get_hierarchical_clusters(returns: pd.DataFrame, threshold: float = 0.5, max_clusters: int = 25) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes averaged distance matrix and performs Ward Linkage clustering.
    Returns (cluster_ids, linkage_matrix).
    """
    if returns.empty:
        return np.array([]), np.array([])

    lookbacks = [60, 120, 200]
    available_len = len(returns)
    valid_lookbacks = [l for l in lookbacks if l <= available_len] or [available_len]

    dist_matrices = []
    for l in valid_lookbacks:
        corr = get_robust_correlation(returns.tail(l))
        dist_matrices.append(np.sqrt(0.5 * (1 - corr.values.clip(-1, 1))))

    avg_dist = np.mean(dist_matrices, axis=0)
    avg_dist = (avg_dist + avg_dist.T) / 2
    np.fill_diagonal(avg_dist, 0)

    link = sch.linkage(squareform(avg_dist, checks=False), method="ward")
    cluster_ids = sch.fcluster(link, t=threshold, criterion="distance") if threshold > 0 else sch.fcluster(link, t=max_clusters, criterion="maxclust")

    return cluster_ids, link


def run_selection(
    returns: pd.DataFrame,
    raw_candidates: List[Dict[str, Any]],
    stats_df: Optional[pd.DataFrame] = None,
    top_n: int = 2,
    threshold: float = 0.5,
    max_clusters: int = 25,
    m_gate: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Core selection logic that operates on DataFrames.
    """
    if returns.columns.empty or not raw_candidates:
        return []

    candidate_map = {c["symbol"]: c for c in raw_candidates}

    cluster_ids, link = get_hierarchical_clusters(returns, threshold, max_clusters)

    clusters: Dict[int, List[str]] = {}
    for sym, c_id in zip(returns.columns, cluster_ids):
        cid = int(c_id)
        if cid not in clusters:
            clusters[cid] = []
        clusters[cid].append(str(sym))

    # --- ALPHA SCORES ---
    settings = get_settings()
    if settings.features.feat_xs_momentum:
        # 1. CROSS-SECTIONAL MOMENTUM & ALPHA SCORES (Unified XS)
        # We calculate these for the entire universe to ensure true XS ranking
        mom_all = returns.mean() * 252
        vol_all = returns.std() * np.sqrt(252)
        stab_all = 1.0 / (vol_all + 1e-9)
        liq_all = pd.Series({s: calculate_liquidity_score(s, candidate_map) for s in returns.columns})
        conv_all = pd.Series(0.0, index=returns.columns)
        if stats_df is not None:
            common = [s for s in returns.columns if s in stats_df.index]
            if common:
                conv_all.loc[common] = stats_df.loc[common, "Antifragility_Score"]

        # Unified Execution Alpha (XS) using rank_series for robustness
        alpha_scores = 0.3 * rank_series(mom_all) + 0.2 * rank_series(stab_all) + 0.2 * rank_series(conv_all) + 0.3 * rank_series(liq_all)
    else:
        # Legacy placeholder - will be calculated per cluster
        alpha_scores = pd.Series(0.0, index=returns.columns)

    selected_symbols = []
    for c_id, symbols in clusters.items():
        # Sub-selection within clusters
        sub_rets = returns.loc[:, symbols]
        if isinstance(sub_rets, pd.Series):
            sub_rets = sub_rets.to_frame()

        # Dynamic Top N based on Cluster Diversity
        actual_top_n = top_n
        if settings.features.feat_dynamic_selection and len(symbols) > 1:
            c_corr = get_robust_correlation(cast(pd.DataFrame, sub_rets))
            # Mean pairwise correlation excluding diagonal
            n_syms = len(symbols)
            upper_indices = np.triu_indices(n_syms, k=1)
            mean_c = float(np.mean(c_corr.values[upper_indices])) if n_syms > 1 else 1.0
            # Higher diversity -> more assets
            # If mean_c is 0.2 (diverse), diversity is 0.8. If top_n=2, actual_top_n=round(2 * 0.8 + 0.5)=2
            # If mean_c is 0.9 (redundant), diversity is 0.1. If top_n=2, actual_top_n=round(2 * 0.1 + 0.5)=1
            actual_top_n = max(1, int(round(top_n * (1.0 - mean_c) + 0.5)))

        # MOMENTUM GATE (Local window)
        window = min(60, len(sub_rets))
        sub_tail = sub_rets.tail(window)
        cum_rets = (1 + sub_tail).prod() - 1
        m_winners = cum_rets[cum_rets >= m_gate].index.tolist()

        if not settings.features.feat_xs_momentum:
            # LEGACY: Local normalization within cluster
            mom_local = sub_rets.mean() * 252
            vol_local = sub_rets.std() * np.sqrt(252)
            stab_local = 1.0 / (vol_local + 1e-9)
            conv_local = pd.Series(0.0, index=symbols)
            if stats_df is not None:
                common_local = [s for s in symbols if s in stats_df.index]
                if common_local:
                    conv_local.loc[common_local] = stats_df.loc[common_local, "Antifragility_Score"]
            liq_local = pd.Series({s: calculate_liquidity_score(s, candidate_map) for s in symbols})

            cluster_alpha = 0.3 * normalize_series(mom_local) + 0.2 * normalize_series(stab_local) + 0.2 * normalize_series(conv_local) + 0.3 * normalize_series(liq_local)
            alpha_scores.loc[symbols] = cluster_alpha

        id_to_best: Dict[str, str] = {}
        for s in symbols:
            ident = candidate_map.get(s, {}).get("identity", s)
            if ident not in id_to_best or alpha_scores[s] > alpha_scores[id_to_best[ident]]:
                id_to_best[ident] = s

        uniques = list(id_to_best.values())

        # LONG selection
        longs = [s for s in uniques if candidate_map.get(s, {}).get("direction", "LONG") == "LONG" and s in m_winners]
        if longs:
            # alpha_scores.loc[longs] returns a Series
            top = cast(pd.Series, alpha_scores.loc[longs]).sort_values(ascending=False).head(actual_top_n).index.tolist()
            selected_symbols.extend([str(s) for s in top])

        # SHORT selection
        shorts = [s for s in uniques if candidate_map.get(s, {}).get("direction") == "SHORT" and s in m_winners]
        if shorts:
            top = cast(pd.Series, alpha_scores.loc[shorts]).sort_values(ascending=False).head(actual_top_n).index.tolist()
            selected_symbols.extend([str(s) for s in top])

    return [candidate_map[s] if s in candidate_map else {"symbol": s, "direction": "LONG"} for s in selected_symbols]


def natural_selection(
    returns_path: str = "data/lakehouse/portfolio_returns.pkl",
    meta_path: str = "data/lakehouse/portfolio_candidates_raw.json",
    stats_path: str = "data/lakehouse/antifragility_stats.json",
    output_path: str = "data/lakehouse/portfolio_candidates.json",
    top_n_per_cluster: Optional[int] = None,
    dist_threshold: Optional[float] = None,
    max_clusters: int = 25,
    min_momentum_score: Optional[float] = None,
):
    settings = get_settings()
    top_n = top_n_per_cluster if top_n_per_cluster is not None else settings.top_n
    threshold = dist_threshold if dist_threshold is not None else settings.threshold
    m_gate = min_momentum_score if min_momentum_score is not None else settings.min_momentum_score

    run_dir = settings.prepare_summaries_run_dir()
    ledger = None
    if settings.features.feat_audit_ledger:
        ledger = AuditLedger(run_dir)

    if not os.path.exists(returns_path) or not os.path.exists(meta_path):
        logger.error("Data missing.")
        return

    with open(returns_path, "rb") as f_in:
        returns = cast(pd.DataFrame, pd.read_pickle(f_in))

    if ledger:
        ledger.record_intent(step="natural_selection", params={"top_n": top_n, "threshold": threshold}, input_hashes={"returns": get_df_hash(returns)})

    with open(meta_path, "r") as f_meta:
        raw_candidates = json.load(f_meta)

    stats_df = pd.read_json(stats_path).set_index("Symbol") if os.path.exists(stats_path) else None

    winners = run_selection(returns, raw_candidates, stats_df, top_n, threshold, max_clusters, m_gate)

    with open(output_path, "w") as f_out:
        json.dump(winners, f_out, indent=2)

    if ledger:
        ledger.record_outcome(step="natural_selection", status="success", output_hashes={"candidates": hashlib.sha256(json.dumps(winners).encode()).hexdigest()}, metrics={"n_winners": len(winners)})
    logger.info(f"Natural Selection Complete: {len(winners)} candidates.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--max-clusters", type=int, default=25)
    parser.add_argument("--min-momentum", type=float)
    args = parser.parse_args()
    natural_selection(top_n_per_cluster=args.top_n, dist_threshold=args.threshold, max_clusters=args.max_clusters, min_momentum_score=args.min_momentum)
