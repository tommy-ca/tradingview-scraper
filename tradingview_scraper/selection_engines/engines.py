import logging
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform

from tradingview_scraper.selection_engines.base import BaseSelectionEngine, SelectionRequest, SelectionResponse
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.predictability import (
    calculate_efficiency_ratio,
    calculate_hurst_exponent,
    calculate_permutation_entropy,
)
from tradingview_scraper.utils.scoring import (
    calculate_liquidity_score,
    calculate_mps_score,
    normalize_series,
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

    if len(returns.columns) < 2:
        return np.array([1]), np.array([])

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
        return self._select_additive_core(
            returns,
            raw_candidates,
            stats_df,
            request,
            weights={"momentum": 0.4, "stability": 0.2, "antifragility": 0.2, "liquidity": 0.2, "fragility": -0.1},
            methods={"momentum": "rank", "stability": "rank", "liquidity": "rank", "antifragility": "rank", "survival": "rank", "efficiency": "rank", "entropy": "rank", "hurst_clean": "rank"},
        )

    def _select_additive_core(
        self,
        returns: pd.DataFrame,
        raw_candidates: List[Dict[str, Any]],
        stats_df: Optional[pd.DataFrame],
        request: SelectionRequest,
        weights: Dict[str, float],
        methods: Dict[str, str],
        clipping_sigma: float = 3.0,
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
        regime_all = pd.Series(1.0, index=returns.columns)

        # Predictability Metrics
        lookback = min(len(returns), 64)
        pe_all = pd.Series({s: calculate_permutation_entropy(returns[s].values[-lookback:]) for s in returns.columns})
        er_all = pd.Series({s: calculate_efficiency_ratio(returns[s].values[-lookback:]) for s in returns.columns})
        hurst_all = pd.Series({s: calculate_hurst_exponent(returns[s].values) for s in returns.columns})

        if stats_df is not None:
            common = [s for s in returns.columns if s in stats_df.index]
            if common:
                af_all.loc[common] = stats_df.loc[common, "Antifragility_Score"]
                if "Fragility_Score" in stats_df.columns:
                    frag_all.loc[common] = stats_df.loc[common, "Fragility_Score"]
                if "Regime_Survival_Score" in stats_df.columns:
                    regime_all.loc[common] = stats_df.loc[common, "Regime_Survival_Score"]

        # 2. Additive Scoring
        from tradingview_scraper.utils.scoring import map_to_probability

        # Mapping to normalized space [0, 1] using factor-specific methods
        metrics_raw = {
            "momentum": mom_all,
            "stability": stab_all,
            "liquidity": liq_all,
            "antifragility": af_all,
            "survival": regime_all,
            "efficiency": er_all,
            "entropy": 1.0 - pe_all,  # High entropy = low score
            "hurst_clean": 1.0 - abs(hurst_all - 0.5) * 2.0,  # 0.5 = low score
            "fragility": -frag_all,  # High fragility = low score
        }

        metrics_norm = {}
        for name, series in metrics_raw.items():
            method = methods.get(name, "rank")
            metrics_norm[name] = map_to_probability(series, method=method, sigma=clipping_sigma)

        alpha_scores = pd.Series(0.0, index=returns.columns)
        for name, w in weights.items():
            if name in metrics_norm:
                alpha_scores += w * metrics_norm[name]

        selected_symbols = []
        audit_clusters = {}
        warnings = []

        for c_id, symbols in clusters.items():
            sub_rets = returns.loc[:, symbols]
            if isinstance(sub_rets, pd.Series):
                sub_rets = sub_rets.to_frame()

            actual_top_n = request.top_n
            # Dynamic selection logic omitted for pure V2/V2.1 comparison unless requested

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
        return SelectionResponse(winners=winners, audit_clusters=audit_clusters, spec_version=getattr(self, "spec_version", "2.0"), warnings=warnings, vetoes={}, metrics={})


class SelectionEngineV2_1(SelectionEngineV2):
    """
    v2.1: Tuned CARS model.
    - Additive Rank-Sum scoring with 8 metrics.
    - Optimized weights from Global Robust HPO.
    """

    @property
    def name(self) -> str:
        return "v2.1"

    def __init__(self):
        super().__init__()
        self.spec_version = "2.1"

    def select(
        self,
        returns: pd.DataFrame,
        raw_candidates: List[Dict[str, Any]],
        stats_df: Optional[pd.DataFrame],
        request: SelectionRequest,
    ) -> SelectionResponse:
        settings = get_settings()
        weights = settings.features.weights_v2_1_global
        methods = settings.features.normalization_methods_v2_1
        sigma = settings.features.clipping_sigma_v2_1
        return self._select_additive_core(returns, raw_candidates, stats_df, request, weights=weights, methods=methods, clipping_sigma=sigma)


class SelectionEngineV3(BaseSelectionEngine):
    """
    Multiplicative Probability Scoring (MPS 3.0) + Operation Darwin Vetoes.
    Now enhanced with Spectral Predictability Filters (PE, Hurst, ER).
    """

    def __init__(self):
        super().__init__()
        self.kappa_threshold = 1e6
        self.eci_hurdle = 0.02
        self.spec_version = "3.0"

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
        return self._select_v3_core(returns, raw_candidates, stats_df, request)

    def _calculate_alpha_scores(self, mps_metrics: Dict[str, pd.Series], methods: Dict[str, str], frag_penalty: pd.Series) -> pd.Series:
        """
        Default V3 Multiplicative Scoring.
        Only includes Efficiency/Entropy if feature flags are enabled.
        """
        settings = get_settings()
        filtered_metrics = {k: v for k, v in mps_metrics.items() if k not in ["efficiency", "entropy", "hurst_clean"]}

        if settings.features.feat_efficiency_scoring:
            filtered_metrics["efficiency"] = mps_metrics["efficiency"]

        # V3.1 baseline doesn't include entropy/hurst in multiplicative score yet

        mps = calculate_mps_score(filtered_metrics, methods=methods)
        return mps * (1.0 - frag_penalty)

    def _select_v3_core(
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

        # Asset Predictability Metrics
        lookback = min(len(returns), 64)
        pe_all = pd.Series({s: calculate_permutation_entropy(returns[s].values[-lookback:]) for s in returns.columns})
        er_all = pd.Series({s: calculate_efficiency_ratio(returns[s].values[-lookback:]) for s in returns.columns})
        hurst_all = pd.Series({s: calculate_hurst_exponent(returns[s].values) for s in returns.columns})

        from tradingview_scraper.utils.predictability import calculate_dwt_turbulence, calculate_stationarity_score

        dwt_all = pd.Series({s: calculate_dwt_turbulence(returns[s].values[-lookback:]) for s in returns.columns})
        adf_all = pd.Series({s: calculate_stationarity_score(returns[s].values[-lookback:]) for s in returns.columns})

        # Higher-Order Moments
        skew_all = returns.skew()
        kurt_all = returns.kurtosis()

        if stats_df is not None:
            common = [s for s in returns.columns if s in stats_df.index]
            if common:
                af_all.loc[common] = stats_df.loc[common, "Antifragility_Score"]
                if "Fragility_Score" in stats_df.columns:
                    frag_all.loc[common] = stats_df.loc[common, "Fragility_Score"]
                if "Regime_Survival_Score" in stats_df.columns:
                    regime_all.loc[common] = stats_df.loc[common, "Regime_Survival_Score"]

        # V3 Multiplicative Selection (Operation Darwin)
        mps_metrics = {
            "momentum": mom_all,
            "stability": stab_all,
            "liquidity": liq_all,
            "antifragility": af_all,
            "survival": regime_all,
            "efficiency": er_all,
            "entropy": (1.0 - pe_all).clip(0, 1),  # High entropy = low probability
            "hurst_clean": (1.0 - abs(hurst_all - 0.5) * 2.0).clip(0, 1),  # 0.5 = low probability
        }
        methods = {
            "survival": "cdf",
            "liquidity": "cdf",
            "momentum": "rank",
            "stability": "rank",
            "antifragility": "rank",
            "efficiency": "cdf",
            "entropy": "rank",
            "hurst_clean": "rank",
        }

        # Scoring Standard (Overridable)
        max_frag = float(frag_all.max())
        frag_penalty = (frag_all / (max_frag if max_frag != 0 else 1.0)).fillna(0) * 0.5
        alpha_scores = self._calculate_alpha_scores(mps_metrics, methods, frag_penalty)

        # V3 Condition Number Check (Numerical Stability Gate)
        force_aggressive_pruning = False
        kappa = 1.0
        corr = get_robust_correlation(returns)
        if not corr.empty:
            eigenvalues = np.linalg.eigvalsh(corr.values)
            min_ev = np.abs(eigenvalues).min()
            kappa = float(eigenvalues.max() / (min_ev + 1e-15))
            if kappa > self.kappa_threshold:
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

        # Spectral Predictability Vetoes (New in 2026-01-01) - Rollout Gate
        if settings.features.feat_predictability_vetoes:
            for s in returns.columns:
                if str(s) in disqualified:
                    continue

                pe = float(pe_all[s])
                if pe > settings.features.entropy_max_threshold:
                    _record_veto(str(s), f"High Entropy ({pe:.4f})")
                    continue

                er = float(er_all[s])
                if er < settings.features.efficiency_min_threshold:
                    _record_veto(str(s), f"Low Efficiency ({er:.4f})")
                    continue

                h = float(hurst_all[s])
                if settings.features.hurst_random_walk_min < h < settings.features.hurst_random_walk_max:
                    # Discard random walk zone
                    _record_veto(str(s), f"Random Walk zone (Hurst={h:.4f})")
                    continue
        else:
            logger.debug("Predictability vetoes skipped (feature flag disabled)")

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
            # Use institutional floor if ADV is missing or near-zero
            adv = float(meta.get("value_traded") or meta.get("Value.Traded") or 1e8)
            if adv <= 0:
                adv = 1e8

            vol_val = float(vol_all[s]) if s in vol_all.index else 0.5
            # Cap ECI impact at 10% to prevent numerical blowups in illiquid data
            eci = min(0.10, float(vol_val * np.sqrt(order_size / adv)))

            annual_alpha = float(mom_all[s]) if s in mom_all.index else 0.0
            if annual_alpha - eci < self.eci_hurdle:
                _record_veto(str(s), f"High ECI ({eci:.4f}) relative to Alpha ({annual_alpha:.4f})")

        for s in disqualified:
            alpha_scores.loc[s] = -1.0

        # Additional Metrics for Response
        metrics["kappa"] = kappa
        metrics["n_disqualified"] = len(disqualified)
        metrics["alpha_scores"] = alpha_scores.to_dict()
        metrics["predictability"] = {
            "avg_pe": float(pe_all.mean()),
            "avg_er": float(er_all.mean()),
            "avg_hurst": float(hurst_all.mean()),
        }

        # Raw Metrics for HPO (Phase 4 Normalization Audit)
        metrics["raw_metrics"] = {
            "momentum": mom_all.to_dict(),
            "stability": stab_all.to_dict(),
            "liquidity": liq_all.to_dict(),
            "antifragility": af_all.to_dict(),
            "survival": regime_all.to_dict(),
            "efficiency": er_all.to_dict(),
            "entropy": pe_all.to_dict(),
            "hurst": hurst_all.to_dict(),
            "fragility": frag_all.to_dict(),
            "skew": skew_all.to_dict(),
            "kurtosis": kurt_all.to_dict(),
            "dwt": dwt_all.to_dict(),
            "adf": adf_all.to_dict(),
        }

        # HPO Support: Record raw component probabilities P_i
        from tradingview_scraper.utils.scoring import map_to_probability

        component_probs = {}
        for name, series in mps_metrics.items():
            method = methods.get(name, "rank")
            component_probs[name] = map_to_probability(series, method=method).to_dict()

        # Add PE, Hurst too
        component_probs["entropy"] = (1.0 - pe_all).clip(0, 1).to_dict()
        component_probs["hurst_clean"] = (1.0 - abs(hurst_all - 0.5) * 2.0).clip(0, 1).to_dict()
        metrics["component_probs"] = component_probs

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

        return SelectionResponse(winners=winners, audit_clusters=serializable_clusters, spec_version=self.spec_version, warnings=warnings, vetoes=vetoes, metrics=metrics)


class SelectionEngineV3_1(SelectionEngineV3):
    """
    v3.1: Relaxed V3 logic.
    - Kappa threshold raised to 1e18 (prevent permanent panic).
    - ECI Hurdle lowered to 0.5% (allow lower-alpha defensive assets).
    """

    def __init__(self):
        super().__init__()
        self.kappa_threshold = 1e18
        self.eci_hurdle = 0.005
        self.spec_version = "3.1"

    @property
    def name(self) -> str:
        return "v3.1"


class SelectionEngineV3_2(SelectionEngineV3_1):
    """
    v3.2: Log-MPS Standard.
    - Uses additive log-probabilities for numerical stability.
    - Component weights omega are tunable via HPO (Optuna).
    - Integrated predictability filters.
    """

    def __init__(self):
        super().__init__()
        self.spec_version = "3.2"
        # Optimized weights (will be updated via Phase 3 HPO)
        # Defaults to 1.0 for all components (parity with v3.1)
        self.weights = {
            "momentum": 1.0,
            "stability": 1.0,
            "liquidity": 1.0,
            "antifragility": 1.0,
            "survival": 1.0,
            "efficiency": 1.0,
        }

    @property
    def name(self) -> str:
        return "v3.2"

    def select(
        self,
        returns: pd.DataFrame,
        raw_candidates: List[Dict[str, Any]],
        stats_df: Optional[pd.DataFrame],
        request: SelectionRequest,
    ) -> SelectionResponse:
        settings = get_settings()
        if not settings.features.feat_selection_logmps:
            # Fallback to v3.1 logic if flag is off
            logger.debug("feat_selection_logmps disabled, falling back to v3.1 multiplicative logic")
            engine_v31 = SelectionEngineV3_1()
            return engine_v31.select(returns, raw_candidates, stats_df, request)

        # Global Robust Weighting (Validated 2026-01-02)
        self.weights = settings.features.weights_global
        logger.info("Using Global Robust weights for Selection v3.2")

        return self._select_v3_core(returns, raw_candidates, stats_df, request)

    def _calculate_alpha_scores(self, mps_metrics: Dict[str, pd.Series], methods: Dict[str, str], frag_penalty: pd.Series) -> pd.Series:
        """
        Calculates scores using additive log-probabilities: Score = sum( omega_i * ln(P_i) ).
        Includes predictability metrics (Efficiency, Entropy, Hurst) in the sum.
        """
        from tradingview_scraper.utils.scoring import map_to_probability

        # 1. Prepare ALL components (Core + Predictability)
        # We need to access the metrics from the calling context if possible,
        # or we just rely on mps_metrics being pre-populated.
        # Wait, _select_v3_core doesn't know about predictability in mps_metrics.
        # I should have injected them there.

        # 2. Compute individual probabilities P_i
        probs: Dict[str, pd.Series] = {}
        for name, series in mps_metrics.items():
            method = methods.get(name, "rank")
            probs[name] = map_to_probability(series, method=method)

        # 3. Sum log-probabilities
        floor = 1e-9
        log_score = pd.Series(0.0, index=frag_penalty.index)

        for name, p_series in probs.items():
            omega = self.weights.get(name, 1.0)
            log_score += omega * np.log(p_series.clip(lower=floor))

        # Log-based penalty: log(1 - penalty)
        penalty_factor = (1.0 - frag_penalty).clip(lower=floor)
        log_score += np.log(penalty_factor)

        # Return exponential to stay in probability-like space [0, 1] for ranking compatibility
        result = np.exp(log_score)
        return cast(pd.Series, result)


class SelectionEngineV2_0(BaseSelectionEngine):
    """
    Original local normalization within clusters.
    Renamed from 'legacy' back to 'v2.0' for standard benchmarking.
    """

    @property
    def name(self) -> str:
        return "v2.0"

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

            # V2.0: Local normalization within cluster
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
        return SelectionResponse(winners=winners, audit_clusters=audit_clusters, spec_version="2.0", warnings=warnings, vetoes={}, metrics={})
