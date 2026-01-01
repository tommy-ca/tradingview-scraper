import logging
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform

from tradingview_scraper.selection_engines.base import BaseSelectionEngine, SelectionRequest, SelectionResponse
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.scoring import (
    calculate_liquidity_score,
    calculate_mps_score,
    normalize_series,
    rank_series,
)

logger = logging.getLogger("selection_engines")


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
        if not corr.empty:
            dist_matrices.append(np.sqrt(0.5 * (1 - corr.values.clip(-1, 1))))

    if not dist_matrices:
        return np.array([1] * len(returns.columns)), np.array([])

    avg_dist = np.mean(dist_matrices, axis=0)
    avg_dist = (avg_dist + avg_dist.T) / 2
    np.fill_diagonal(avg_dist, 0)

    link = sch.linkage(squareform(avg_dist, checks=False), method="ward")
    cluster_ids = sch.fcluster(link, t=threshold, criterion="distance") if threshold > 0 else sch.fcluster(link, t=max_clusters, criterion="maxclust")

    return cluster_ids, link


class SelectionEngineV2(BaseSelectionEngine):
    """
    Unified Composite Alpha-Risk Score (CARS 2.0).
    Additive scoring: Score = 0.4*Mom + 0.2*Stab + 0.2*AF + 0.2*Liq.
    """

    @property
    def name(self) -> str:
        return "v2"

    def select(
        self,
        returns: pd.DataFrame,
        raw_candidates: List[Dict[str, Any]],
        stats_df: Optional[pd.DataFrame],
        request: SelectionRequest,
    ) -> SelectionResponse:
        candidate_map = {c["symbol"]: c for c in raw_candidates}
        settings = get_settings()

        cluster_ids, _ = get_hierarchical_clusters(returns, request.threshold, request.max_clusters)
        clusters: Dict[int, List[str]] = {}
        for sym, c_id in zip(returns.columns, cluster_ids):
            cid = int(c_id)
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(str(sym))

        # 1. Component Extraction
        mom_all = returns.mean() * 252
        vol_all = returns.std() * np.sqrt(252)
        stab_all = 1.0 / (vol_all + 1e-9)
        liq_all = pd.Series({s: calculate_liquidity_score(str(s), candidate_map) for s in returns.columns})
        af_all = pd.Series(0.5, index=returns.columns)
        frag_all = pd.Series(0.0, index=returns.columns)

        if stats_df is not None:
            common = [s for s in returns.columns if s in stats_df.index]
            if common:
                af_all.loc[common] = stats_df.loc[common, "Antifragility_Score"]
                if "Fragility_Score" in stats_df.columns:
                    frag_all.loc[common] = stats_df.loc[common, "Fragility_Score"]

        # Unified Composite Alpha-Risk Score (CARS 2.0)
        alpha_scores = 0.4 * rank_series(mom_all) + 0.2 * rank_series(stab_all) + 0.2 * rank_series(af_all) + 0.2 * rank_series(liq_all) - 0.1 * rank_series(frag_all)

        selected_symbols = []
        audit_clusters = {}
        warnings = []

        for c_id, symbols in clusters.items():
            sub_rets = returns.loc[:, symbols]
            if isinstance(sub_rets, pd.Series):
                sub_rets = sub_rets.to_frame()

            actual_top_n = request.top_n
            if settings.features.feat_dynamic_selection and len(symbols) > 1:
                c_corr = get_robust_correlation(cast(pd.DataFrame, sub_rets))
                n_syms = len(symbols)
                if n_syms > 1:
                    upper_indices = np.triu_indices(n_syms, k=1)
                    mean_c = float(np.mean(c_corr.values[upper_indices]))
                    actual_top_n = max(1, int(round(request.top_n * (1.0 - mean_c) + 0.5)))

            # MOMENTUM GATE (Local window)
            window = min(60, len(sub_rets))
            sub_tail = sub_rets.tail(window)
            cum_rets = (1 + sub_tail).prod() - 1
            m_winners = cum_rets[cum_rets >= request.min_momentum_score].index.tolist()

            id_to_best: Dict[str, str] = {}
            for s in symbols:
                ident = candidate_map.get(s, {}).get("identity", s)
                if ident not in id_to_best or alpha_scores[s] > alpha_scores[id_to_best[ident]]:
                    id_to_best[ident] = s

            uniques = list(id_to_best.values())
            longs = [s for s in uniques if candidate_map.get(s, {}).get("direction", "LONG") == "LONG" and s in m_winners]
            c_selected = []
            if longs:
                top = cast(pd.Series, alpha_scores.loc[longs]).sort_values(ascending=False).head(actual_top_n).index.tolist()
                c_selected.extend([str(s) for s in top])

            shorts = [s for s in uniques if candidate_map.get(s, {}).get("direction") == "SHORT" and s in m_winners]
            if shorts:
                top = cast(pd.Series, alpha_scores.loc[shorts]).sort_values(ascending=False).head(actual_top_n).index.tolist()
                c_selected.extend([str(s) for s in top])

            selected_symbols.extend(c_selected)
            audit_clusters[int(c_id)] = {"size": len(symbols), "selected": c_selected}

        winners = [candidate_map[s] if s in candidate_map else {"symbol": s, "direction": "LONG"} for s in selected_symbols]
        return SelectionResponse(winners=winners, audit_clusters=audit_clusters, spec_version="2.0", warnings=warnings, vetoes={}, metrics={})


class SelectionEngineV3(BaseSelectionEngine):
    """
    Multiplicative Probability Scoring (MPS 3.0) + Operation Darwin Vetoes.
    """

    @property
    def name(self) -> str:
        return "v3"

    def select(
        self,
        returns: pd.DataFrame,
        raw_candidates: List[Dict[str, Any]],
        stats_df: Optional[pd.DataFrame],
        request: SelectionRequest,
    ) -> SelectionResponse:
        candidate_map = {c["symbol"]: c for c in raw_candidates}
        settings = get_settings()
        warnings = []
        metrics: Dict[str, Any] = {}
        vetoes: Dict[str, List[str]] = {}

        cluster_ids, _ = get_hierarchical_clusters(returns, request.threshold, request.max_clusters)
        clusters: Dict[int, List[str]] = {}
        for sym, c_id in zip(returns.columns, cluster_ids):
            cid = int(c_id)
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(str(sym))

        # 1. Component Extraction
        mom_all = returns.mean() * 252
        vol_all = returns.std() * np.sqrt(252)
        stab_all = 1.0 / (vol_all + 1e-9)
        liq_all = pd.Series({s: calculate_liquidity_score(str(s), candidate_map) for s in returns.columns})
        af_all = pd.Series(0.5, index=returns.columns)
        frag_all = pd.Series(0.0, index=returns.columns)
        regime_all = pd.Series(1.0, index=returns.columns)

        if stats_df is not None:
            common = [s for s in returns.columns if s in stats_df.index]
            if common:
                af_all.loc[common] = stats_df.loc[common, "Antifragility_Score"]
                if "Fragility_Score" in stats_df.columns:
                    frag_all.loc[common] = stats_df.loc[common, "Fragility_Score"]
                if "Regime_Survival_Score" in stats_df.columns:
                    regime_all.loc[common] = stats_df.loc[common, "Regime_Survival_Score"]

        # V3 Multiplicative Selection (Operation Darwin)
        mps_metrics = {"momentum": mom_all, "stability": stab_all, "liquidity": liq_all, "antifragility": af_all, "survival": regime_all}
        methods = {"survival": "cdf", "liquidity": "cdf", "momentum": "rank", "stability": "rank", "antifragility": "rank"}
        mps = calculate_mps_score(mps_metrics, methods=methods)

        max_frag = float(frag_all.max())
        frag_penalty = (frag_all / (max_frag if max_frag != 0 else 1.0)).fillna(0) * 0.5
        alpha_scores = mps * (1.0 - frag_penalty)

        # V3 Condition Number Check (Numerical Stability Gate)
        force_aggressive_pruning = False
        kappa = 1.0
        corr = get_robust_correlation(returns)
        if not corr.empty:
            eigenvalues = np.linalg.eigvalsh(corr.values)
            min_ev = np.abs(eigenvalues).min()
            kappa = float(eigenvalues.max() / (min_ev + 1e-15))
            if kappa > 1e6:
                msg = f"High Condition Number (kappa={kappa:.2e}). Forcing aggressive pruning."
                logger.warning(msg)
                warnings.append(msg)
                force_aggressive_pruning = True

        # V3 Execution & Metadata Vetoes
        disqualified = set()

        def _record_veto(sym: str, reason: str):
            if sym not in vetoes:
                vetoes[sym] = []
            vetoes[sym].append(reason)
            disqualified.add(sym)
            logger.warning(f"Vetoing {sym}: {reason}")
            warnings.append(f"Vetoing {sym}: {reason}")

        # Absolute Survival Veto
        for s in returns.columns:
            s_score = float(regime_all[s]) if s in regime_all.index else 1.0
            if s_score < 0.1:
                _record_veto(str(s), f"Failed Darwinian Health Gate (Regime Survival={s_score:.4f})")

        # Metadata Completeness
        required_meta = ["tick_size", "lot_size", "price_precision"]
        for s in returns.columns:
            if str(s) in disqualified:
                continue
            meta = candidate_map.get(str(s), {})
            missing = [f for f in required_meta if f not in meta]
            if missing:
                _record_veto(str(s), f"Missing metadata {missing}")

        # ECI (Estimated Cost of Implementation)
        order_size = 1e6
        for s in returns.columns:
            if str(s) in disqualified:
                continue
            meta = candidate_map.get(str(s), {})
            adv = float(meta.get("value_traded") or meta.get("Value.Traded") or 1e-9)

            # SAFE ACCESS: fix diagnostics
            vol_val = float(vol_all[s]) if s in vol_all.index else 0.5
            eci = float(vol_val * np.sqrt(order_size / adv))

            annual_alpha = float(mom_all[s]) if s in mom_all.index else 0.0
            if annual_alpha - eci < 0.02:
                _record_veto(str(s), f"High ECI ({eci:.4f}) relative to Alpha ({annual_alpha:.4f})")

        for s in disqualified:
            alpha_scores.loc[s] = -1.0

        # Additional Metrics for Response
        metrics["kappa"] = kappa
        metrics["n_disqualified"] = len(disqualified)
        metrics["alpha_scores"] = alpha_scores.to_dict()

        # Calculate avg_eci safely
        valid_advs = [float(candidate_map.get(str(s), {}).get("value_traded") or 1e-9) for s in returns.columns]

        avg_eci_vals = []
        for s, adv in zip(returns.columns, valid_advs):
            v = float(vol_all[s]) if s in vol_all.index else 0.5
            avg_eci_vals.append(v * np.sqrt(1e6 / adv))
        metrics["avg_eci"] = float(np.mean(avg_eci_vals))

        selected_symbols = []
        audit_clusters = {}
        for c_id, symbols in clusters.items():
            symbols = [s for s in symbols if s not in disqualified]
            if not symbols:
                continue

            sub_rets = returns.loc[:, symbols]
            if isinstance(sub_rets, pd.Series):
                sub_rets = sub_rets.to_frame()

            actual_top_n = 1 if force_aggressive_pruning else request.top_n
            if not force_aggressive_pruning and settings.features.feat_dynamic_selection and len(symbols) > 1:
                c_corr = get_robust_correlation(cast(pd.DataFrame, sub_rets))
                n_syms = len(symbols)
                if n_syms > 1:
                    upper_indices = np.triu_indices(n_syms, k=1)
                    mean_c = float(np.mean(c_corr.values[upper_indices]))
                    actual_top_n = max(1, int(round(request.top_n * (1.0 - mean_c) + 0.5)))

            window = min(60, len(sub_rets))
            sub_tail = sub_rets.tail(window)
            cum_rets = (1 + sub_tail).prod() - 1
            m_winners = cum_rets[cum_rets >= request.min_momentum_score].index.tolist()

            id_to_best: Dict[str, str] = {}
            for s in symbols:
                ident = candidate_map.get(s, {}).get("identity", s)
                if ident not in id_to_best or alpha_scores[s] > alpha_scores[id_to_best[ident]]:
                    id_to_best[ident] = s

            uniques = list(id_to_best.values())
            longs = [s for s in uniques if candidate_map.get(s, {}).get("direction", "LONG") == "LONG" and s in m_winners]
            c_selected = []
            if longs:
                top = cast(pd.Series, alpha_scores.loc[longs]).sort_values(ascending=False).head(actual_top_n).index.tolist()
                c_selected.extend([str(s) for s in top])

            shorts = [s for s in uniques if candidate_map.get(s, {}).get("direction") == "SHORT" and s in m_winners]
            if shorts:
                top = cast(pd.Series, alpha_scores.loc[shorts]).sort_values(ascending=False).head(actual_top_n).index.tolist()
                c_selected.extend([str(s) for s in top])

            selected_symbols.extend(c_selected)
            audit_clusters[int(c_id)] = {"size": len(symbols), "selected": c_selected}

        winners = [candidate_map[s] if s in candidate_map else {"symbol": s, "direction": "LONG"} for s in selected_symbols]

        # Ensure JSON serializable audit_clusters
        serializable_clusters = {int(k): v for k, v in audit_clusters.items()}

        return SelectionResponse(winners=winners, audit_clusters=serializable_clusters, spec_version="3.0", warnings=warnings, vetoes=vetoes, metrics=metrics)


class LegacySelectionEngine(BaseSelectionEngine):
    """
    Original local normalization within clusters.
    """

    @property
    def name(self) -> str:
        return "legacy"

    def select(
        self,
        returns: pd.DataFrame,
        raw_candidates: List[Dict[str, Any]],
        stats_df: Optional[pd.DataFrame],
        request: SelectionRequest,
    ) -> SelectionResponse:
        candidate_map = {c["symbol"]: c for c in raw_candidates}
        settings = get_settings()
        alpha_scores = pd.Series(0.0, index=returns.columns)
        warnings = []

        cluster_ids, _ = get_hierarchical_clusters(returns, request.threshold, request.max_clusters)
        clusters: Dict[int, List[str]] = {}
        for sym, c_id in zip(returns.columns, cluster_ids):
            cid = int(c_id)
            if cid not in clusters:
                clusters[cid] = []
            clusters[cid].append(str(sym))

        selected_symbols = []
        audit_clusters = {}

        for c_id, symbols in clusters.items():
            sub_rets = returns.loc[:, symbols]
            if isinstance(sub_rets, pd.Series):
                sub_rets = sub_rets.to_frame()

            actual_top_n = request.top_n
            if settings.features.feat_dynamic_selection and len(symbols) > 1:
                c_corr = get_robust_correlation(cast(pd.DataFrame, sub_rets))
                n_syms = len(symbols)
                if n_syms > 1:
                    upper_indices = np.triu_indices(n_syms, k=1)
                    mean_c = float(np.mean(c_corr.values[upper_indices]))
                    actual_top_n = max(1, int(round(request.top_n * (1.0 - mean_c) + 0.5)))

            window = min(60, len(sub_rets))
            sub_tail = sub_rets.tail(window)
            cum_rets = (1 + sub_tail).prod() - 1
            m_winners = cum_rets[cum_rets >= request.min_momentum_score].index.tolist()

            # LEGACY: Local normalization within cluster
            mom_local = sub_rets.mean() * 252
            vol_local = sub_rets.std() * np.sqrt(252)
            stab_local = 1.0 / (vol_local + 1e-9)
            conv_local = pd.Series(0.0, index=symbols)
            if stats_df is not None:
                common_local = [s for s in symbols if s in stats_df.index]
                if common_local:
                    conv_local.loc[common_local] = stats_df.loc[common_local, "Antifragility_Score"]
            liq_local = pd.Series({s: calculate_liquidity_score(str(s), candidate_map) for s in symbols})

            cluster_alpha = 0.3 * normalize_series(mom_local) + 0.2 * normalize_series(stab_local) + 0.2 * normalize_series(conv_local) + 0.3 * normalize_series(liq_local)
            alpha_scores.loc[symbols] = cluster_alpha

            id_to_best: Dict[str, str] = {}
            for s in symbols:
                ident = candidate_map.get(s, {}).get("identity", s)
                if ident not in id_to_best or alpha_scores[s] > alpha_scores[id_to_best[ident]]:
                    id_to_best[ident] = s

            uniques = list(id_to_best.values())
            longs = [s for s in uniques if candidate_map.get(s, {}).get("direction", "LONG") == "LONG" and s in m_winners]
            c_selected = []
            if longs:
                top = cast(pd.Series, alpha_scores.loc[longs]).sort_values(ascending=False).head(actual_top_n).index.tolist()
                c_selected.extend([str(s) for s in top])

            shorts = [s for s in uniques if candidate_map.get(s, {}).get("direction") == "SHORT" and s in m_winners]
            if shorts:
                top = cast(pd.Series, alpha_scores.loc[shorts]).sort_values(ascending=False).head(actual_top_n).index.tolist()
                c_selected.extend([str(s) for s in top])

            selected_symbols.extend(c_selected)
            audit_clusters[int(c_id)] = {"size": len(symbols), "selected": c_selected}

        winners = [candidate_map[s] if s in candidate_map else {"symbol": s, "direction": "LONG"} for s in selected_symbols]
        return SelectionResponse(winners=winners, audit_clusters=audit_clusters, spec_version="1.0", warnings=warnings, vetoes={}, metrics={})
