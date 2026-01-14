import logging
from typing import Any, Dict, Set

import pandas as pd

from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.settings import get_settings

logger = logging.getLogger("pipelines.selection.policy")


class SelectionPolicyStage(BasePipelineStage):
    """
    Stage 5: Selection Policy.
    Applies vetoes, executes Top-N recruitment per cluster, and handles HTR fallbacks.
    """

    @property
    def name(self) -> str:
        return "SelectionPolicy"

    def execute(self, context: SelectionContext) -> SelectionContext:
        settings = get_settings()
        params = context.params

        # 1. Gather Inputs
        if context.inference_outputs.empty or "alpha_score" not in context.inference_outputs.columns:
            logger.warning("SelectionPolicyStage: No alpha scores found. Returning empty winners.")
            context.winners = []
            return context

        scores = context.inference_outputs["alpha_score"]
        features = context.feature_store
        clusters = context.clusters
        candidate_map = {str(c["symbol"]): c for c in context.raw_pool}

        relaxation_stage = int(params.get("relaxation_stage", 1))
        top_n = int(params.get("top_n", 2))

        # 2. Apply Vetoes
        disqualified = self._apply_vetoes(features, candidate_map, settings, params)

        # 3. Recruitment Loop
        # We perform initial recruitment into a buffer, then prune for diversity and size
        recruitment_buffer: Set[str] = set()

        # Cluster Recruitment
        for cid, symbols in clusters.items():
            non_vetoed = [str(s) for s in symbols if str(s) not in disqualified]
            ranked = sorted(non_vetoed, key=lambda s: float(scores.get(str(s), -1.0)), reverse=True)

            # Select Top N per cluster
            recruitment_buffer.update(ranked[:top_n])

            # STAGE 3: Force Representative if Cluster Empty
            if not ranked[:top_n] and relaxation_stage >= 3 and symbols:
                all_ranked = sorted([str(s) for s in symbols], key=lambda s: float(scores.get(str(s), -1.0)), reverse=True)
                for s in all_ranked:
                    ent = float(features.loc[s, "entropy"]) if s in features.index else 1.0
                    if ent <= 0.999:
                        recruitment_buffer.add(s)
                        break

        # STAGE 4: Balanced Fallback
        if len(recruitment_buffer) < 15 and relaxation_stage >= 4:
            needed = 15 - len(recruitment_buffer)
            valid_pool = [
                str(s)
                for s in scores.index
                if str(s) not in recruitment_buffer and str(s) not in disqualified and (float(features.loc[str(s), "entropy"]) if str(s) in features.index else 1.0) <= 0.999
            ]
            global_ranked = sorted(valid_pool, key=lambda s: float(scores.get(str(s), -1.0)), reverse=True)
            recruitment_buffer.update(global_ranked[:needed])

        # 4. Finalize Winners & Apply Pool Sizing (Pillar 1)
        winners = []

        # Sort buffer by absolute conviction
        sorted_buffer = sorted(list(recruitment_buffer), key=lambda s: float(scores.get(str(s), -1.0)), reverse=True)

        # Institutional Cap: Max 25 assets to maintain high weight fidelity
        # Delegation: Directional balance and other risk constraints are handled in Pillar 3
        target_size = min(25, len(sorted_buffer))
        final_selected = sorted_buffer[:target_size]

        for s in final_selected:
            meta = candidate_map.get(s, {"symbol": s}).copy()
            meta["alpha_score"] = float(scores.get(s, 0.0))
            mom = float(features.loc[s, "momentum"]) if s in features.index else 0.0
            meta["direction"] = "LONG" if mom >= 0 else "SHORT"
            winners.append(meta)

        context.winners = winners
        n_shorts_final = len([w for w in winners if w["direction"] == "SHORT"])
        logger.info(f"Policy Result: {len(winners)} winners recruited ({n_shorts_final} shorts).")
        context.log_event(self.name, "SelectionComplete", {"stage": relaxation_stage, "n_winners": len(winners), "n_vetoed": len(disqualified), "n_shorts": n_shorts_final})

        return context

    def _apply_vetoes(self, features: pd.DataFrame, candidate_map: Dict[str, Any], settings: Any, params: Dict[str, Any]) -> Set[str]:
        disqualified: Set[str] = set()

        # Thresholds
        t_entropy = float(params.get("entropy_max_threshold", settings.features.entropy_max_threshold))
        t_efficiency = float(params.get("efficiency_min_threshold", settings.features.efficiency_min_threshold))

        for s_idx in features.index:
            s = str(s_idx)
            # 1. Metadata Vetoes
            meta = candidate_map.get(s, {})
            if any(f not in meta for f in ["tick_size", "lot_size", "price_precision"]):
                # Allow if benchmark? v3 logic exempts benchmarks.
                pass

            # 2. Predictability Vetoes (if enabled)
            if settings.features.feat_predictability_vetoes:
                ent = float(features.loc[s, "entropy"])
                eff = float(features.loc[s, "efficiency"])
                kurt = float(features.loc[s, "kurtosis"])
                asset_vol_inv = float(features.loc[s, "stability"])
                vol_val = 1.0 / (asset_vol_inv + 1e-9)

                if ent > t_entropy:
                    disqualified.add(s)
                if eff < t_efficiency:
                    disqualified.add(s)
                # CR-630: Tail Risk Hardening
                if kurt > 20.0:  # Institutional "Fat Tail" limit
                    disqualified.add(s)
                if vol_val > 2.5:  # Hard cap on asset-level volatility (250%)
                    disqualified.add(s)

            # 3. Regime Veto (Darwinian)
            surv = float(features.loc[s, "survival"])
            if surv < 0.1:
                disqualified.add(s)

        # Benchmark Exemption
        for b_idx in settings.benchmark_symbols:
            b = str(b_idx)
            if b in disqualified:
                disqualified.remove(b)

        return disqualified
