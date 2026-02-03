from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd

from tradingview_scraper.selection_engines.base import (
    BaseSelectionEngine,
    SelectionRequest,
    SelectionResponse,
    get_hierarchical_clusters,
    get_robust_correlation,
)
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.predictability import (
    calculate_efficiency_ratio,
    calculate_hurst_exponent,
    calculate_permutation_entropy,
)
from tradingview_scraper.utils.scoring import calculate_liquidity_score_vectorized, normalize_series

if TYPE_CHECKING:
    from tradingview_scraper.backtest.models import NumericalWorkspace

logger = logging.getLogger("selection_engines")


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
        raw_candidates: list[dict[str, Any]],
        stats_df: pd.DataFrame | None,
        request: SelectionRequest,
        workspace: NumericalWorkspace | None = None,
    ) -> SelectionResponse:
        return self._select_additive_core(
            returns,
            raw_candidates,
            stats_df,
            request,
            weights={"momentum": 0.4, "stability": 0.2, "antifragility": 0.2, "liquidity": 0.2, "fragility": -0.1},
            methods={
                "momentum": "rank",
                "stability": "rank",
                "liquidity": "rank",
                "antifragility": "rank",
                "survival": "rank",
                "efficiency": "rank",
                "entropy": "rank",
                "hurst_clean": "rank",
            },
            workspace=workspace,
        )

    def _select_additive_core(self, returns, raw_candidates, stats_df, request, weights, methods, clipping_sigma=3.0, workspace=None):
        candidate_map = {c["symbol"]: c for c in raw_candidates}
        settings = get_settings()
        cluster_ids, _ = get_hierarchical_clusters(returns, request.threshold, request.max_clusters)
        clusters = {}
        for sym, c_id in zip(returns.columns, cluster_ids):
            clusters.setdefault(int(c_id), []).append(str(sym))
        mom_all = cast(pd.Series, returns.mean() * 252)
        vol_all = returns.std() * np.sqrt(252)
        stab_all = 1.0 / (vol_all + 1e-9)

        # Vectorized Metadata Extraction
        pool_df = pd.DataFrame(raw_candidates)
        if not pool_df.empty:
            pool_df = pool_df.set_index("symbol")
            pool_df = pool_df.reindex(returns.columns)
        else:
            pool_df = pd.DataFrame(index=returns.columns)

        liq_all = calculate_liquidity_score_vectorized(pool_df)
        af_all, frag_all, regime_all = pd.Series(0.5, index=returns.columns), pd.Series(0.0, index=returns.columns), pd.Series(1.0, index=returns.columns)

        lookback = min(len(returns), 120)

        # Numerical Workspace integration
        perm_counts = workspace.perm_counts if workspace else None
        segment_buffer = workspace.segment_buffer if workspace else None

        pe_all = returns.apply(lambda col: calculate_permutation_entropy(col.tail(lookback).to_numpy(), order=5, perm_counts=perm_counts, segment_buffer=segment_buffer))
        er_all = returns.apply(lambda col: calculate_efficiency_ratio(col.tail(lookback).to_numpy()))
        hurst_all = returns.apply(lambda col: calculate_hurst_exponent(col.to_numpy()))

        if stats_df is not None:
            common = [s for s in returns.columns if s in stats_df.index]
            if common:
                af_all.update(stats_df.loc[common, "Antifragility_Score"])
                if "Fragility_Score" in stats_df.columns:
                    frag_all.update(stats_df.loc[common, "Fragility_Score"])
                if "Regime_Survival_Score" in stats_df.columns:
                    regime_all.update(stats_df.loc[common, "Regime_Survival_Score"])
        from tradingview_scraper.utils.scoring import map_to_probability

        metrics_raw = {
            "momentum": mom_all,
            "stability": stab_all,
            "liquidity": liq_all,
            "antifragility": af_all,
            "survival": regime_all,
            "efficiency": er_all,
            "entropy": (1.0 - pe_all.fillna(1.0)),
            "hurst_clean": (1.0 - (hurst_all.fillna(0.5) - 0.5).abs() * 2.0),
            "fragility": -frag_all,
        }
        metrics_norm = {n: map_to_probability(s, method=methods.get(n, "rank"), sigma=clipping_sigma) for n, s in metrics_raw.items()}
        alpha_scores = pd.Series(0.0, index=returns.columns)
        for n, w in weights.items():
            if n in metrics_norm:
                alpha_scores += w * metrics_norm[n]
        selected_symbols_dict, audit_clusters = {}, {}
        for c_id, symbols in clusters.items():
            sub_rets = returns[symbols]
            actual_top_n = max(3, request.top_n)
            if settings.features.feat_dynamic_selection and len(symbols) > 1:
                mean_c = float(get_robust_correlation(sub_rets, shrinkage=settings.features.default_shrinkage_intensity).values[np.triu_indices(len(symbols), k=1)].mean())
                actual_top_n = max(1, int(round(request.top_n * (1.0 - mean_c) + 0.5)))
            id_to_best = {}
            for s in symbols:
                ident = candidate_map.get(s, {}).get("identity", s)
                if ident not in id_to_best or alpha_scores[s] > alpha_scores[id_to_best[ident]]:
                    id_to_best[ident] = s
            uniques = list(id_to_best.values())
            m_win = (1 + sub_rets.tail(60).fillna(0.0)).prod() - 1
            longs = [s for s in uniques if candidate_map.get(s, {}).get("direction", "LONG") == "LONG" and m_win.get(s, 0) >= request.min_momentum_score]
            shorts = [s for s in uniques if candidate_map.get(s, {}).get("direction") == "SHORT" and m_win.get(s, 0) >= request.min_momentum_score]
            c_sel = []
            if longs:
                c_sel.extend(alpha_scores.loc[longs].sort_values(ascending=False).head(actual_top_n).index.tolist())
            if shorts:
                c_sel.extend(alpha_scores.loc[shorts].sort_values(ascending=False).head(actual_top_n).index.tolist())
            for s in c_sel:
                selected_symbols_dict[s] = 1
            audit_clusters[int(c_id)] = {"size": len(symbols), "selected": c_sel}
        winners = [
            ({**candidate_map[s], "alpha_score": float(alpha_scores[s])} if s in candidate_map else {"symbol": s, "direction": "LONG", "alpha_score": float(alpha_scores[s])})
            for s in list(selected_symbols_dict.keys())
        ]
        metrics = {"alpha_scores": alpha_scores.to_dict(), "predictability": {"avg_pe": float(pe_all.mean()), "avg_er": float(er_all.mean()), "avg_hurst": float(hurst_all.mean())}}
        return SelectionResponse(winners=winners, audit_clusters=audit_clusters, spec_version=getattr(self, "spec_version", "2.0"), warnings=[], vetoes={}, metrics=metrics)


class SelectionEngineV2_1(SelectionEngineV2):
    @property
    def name(self) -> str:
        return "v2.1"

    def __init__(self):
        super().__init__()
        self.spec_version = "2.1"

    def select(self, returns, raw_candidates, stats_df, request, workspace=None):
        s = get_settings()
        return self._select_additive_core(
            returns,
            raw_candidates,
            stats_df,
            request,
            weights=s.features.weights_v2_1_global,
            methods=s.features.normalization_methods_v2_1,
            clipping_sigma=s.features.clipping_sigma_v2_1,
            workspace=workspace,
        )


class SelectionEngineV2_0(SelectionEngineV2):
    @property
    def name(self) -> str:
        return "v2.0"

    def select(self, returns, raw_candidates, stats_df, request, workspace=None):
        s, alpha_scores = get_settings(), pd.Series(0.0, index=returns.columns)
        cluster_ids, _ = get_hierarchical_clusters(returns, request.threshold, request.max_clusters)
        clusters = {}
        for sym, c_id in zip(returns.columns, cluster_ids):
            clusters.setdefault(int(c_id), []).append(str(sym))

        # Vectorized Metadata Extraction
        pool_df = pd.DataFrame(raw_candidates)
        if not pool_df.empty:
            pool_df = pool_df.set_index("symbol")
            pool_df = pool_df.reindex(returns.columns)
        else:
            pool_df = pd.DataFrame(index=returns.columns)

        candidate_map = {c["symbol"]: c for c in raw_candidates}
        selected_symbols_dict, audit_clusters = {}, {}
        m_win_all = (1 + returns.tail(60).fillna(0.0)).prod() - 1
        for c_id, symbols in clusters.items():
            sub_rets = returns[symbols]
            actual_top_n = max(3, request.top_n)
            if s.features.feat_dynamic_selection and len(symbols) > 1:
                mean_c = float(get_robust_correlation(sub_rets, shrinkage=s.features.default_shrinkage_intensity).values[np.triu_indices(len(symbols), k=1)].mean())
                actual_top_n = max(1, int(round(request.top_n * (1.0 - mean_c) + 0.5)))
            vol_l = sub_rets.std() * np.sqrt(252)
            conv_l = pd.Series(0.0, index=symbols)
            if stats_df is not None:
                common = [sym for sym in symbols if sym in stats_df.index]
                if common:
                    conv_l.update(stats_df.loc[common, "Antifragility_Score"])

            # Vectorized Metadata for this cluster
            sub_pool = pool_df.loc[symbols]
            liq_l = calculate_liquidity_score_vectorized(sub_pool)

            alpha_scores.loc[symbols] = 0.3 * normalize_series(sub_rets.mean() * 252) + 0.2 * normalize_series(1.0 / (vol_l + 1e-9)) + 0.2 * normalize_series(conv_l) + 0.3 * normalize_series(liq_l)
            id_to_best = {}
            for sym in symbols:
                ident = candidate_map.get(sym, {}).get("identity", sym)
                if ident not in id_to_best or alpha_scores[sym] > alpha_scores[id_to_best.get(ident, sym)]:
                    id_to_best[ident] = sym
            uniques = list(id_to_best.values())
            longs = [sym for sym in uniques if candidate_map.get(sym, {}).get("direction", "LONG") == "LONG" and m_win_all.get(sym, 0) >= request.min_momentum_score]
            shorts = [sym for sym in uniques if candidate_map.get(sym, {}).get("direction") == "SHORT" and m_win_all.get(sym, 0) >= request.min_momentum_score]
            c_sel = []
            if longs:
                c_sel.extend(alpha_scores.loc[longs].sort_values(ascending=False).head(actual_top_n).index.tolist())
            if shorts:
                c_sel.extend(alpha_scores.loc[shorts].sort_values(ascending=False).head(actual_top_n).index.tolist())
            for s_key in c_sel:
                selected_symbols_dict[s_key] = 1
            audit_clusters[int(c_id)] = {"size": len(symbols), "selected": c_sel}
        return SelectionResponse(
            winners=[candidate_map.get(sym, {"symbol": sym, "direction": "LONG"}) for sym in list(selected_symbols_dict.keys())], audit_clusters=audit_clusters, spec_version="2.0"
        )
