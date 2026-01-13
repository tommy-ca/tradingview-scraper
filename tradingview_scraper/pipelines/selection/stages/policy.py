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
        candidate_map = {c["symbol"]: c for c in context.raw_pool}

        relaxation_stage = int(params.get("relaxation_stage", 1))
        top_n = int(params.get("top_n", 2))

        # 2. Apply Vetoes
        disqualified = self._apply_vetoes(features, candidate_map, settings, params)

        # 3. Recruitment Loop
        selected_symbols: Set[str] = set()

        # Cluster Recruitment
        for cid, symbols in clusters.items():
            non_vetoed = [s for s in symbols if s not in disqualified]

            # Sort by Alpha Score
            ranked = sorted(non_vetoed, key=lambda s: scores.get(s, -1.0), reverse=True)

            # Select Top N
            recruits = ranked[:top_n]

            # STAGE 3: Force Representative if Cluster Empty
            if not recruits and relaxation_stage >= 3 and symbols:
                # Find best even if vetoed (unless strictly toxic)
                # v3 Logic: "Find best representative in cluster that isn't hard-vetoed"
                # For v4, let's look at all symbols in cluster, sort by score
                # But we must respect HARD toxicity (Entropy > 0.999)
                all_ranked = sorted(symbols, key=lambda s: scores.get(s, -1.0), reverse=True)
                for s in all_ranked:
                    ent = features.loc[s, "entropy"] if s in features.index else 1.0
                    if ent <= 0.999:
                        recruits.append(s)
                        break

            selected_symbols.update(recruits)

        # STAGE 4: Balanced Fallback
        # If pool < 15, fill from global top score list
        if len(selected_symbols) < 15 and relaxation_stage >= 4:
            needed = 15 - len(selected_symbols)
            # Global rank of valid non-selected assets
            valid_pool = [
                s
                for s in scores.index
                if s not in selected_symbols
                and s not in disqualified
                # Ensure simple toxicity check
                and (features.loc[s, "entropy"] if s in features.index else 1.0) <= 0.999
            ]

            global_ranked = sorted(valid_pool, key=lambda s: scores.get(s, -1.0), reverse=True)
            fallback_recruits = global_ranked[:needed]
            selected_symbols.update(fallback_recruits)
            logger.info(f"Stage 4 Fallback: Recruited {len(fallback_recruits)} assets.")

        # 4. Finalize Winners
        winners = []
        for s in selected_symbols:
            meta = candidate_map.get(s, {"symbol": s})
            # Inject calculated alpha score for downstream use
            meta["alpha_score"] = float(scores.get(s, 0.0))
            # Determine direction (Default LONG for now, v3 does dynamic direction)
            # v4 Logic: We use the direction from discovery (raw_pool) or default LONG
            # If we need dynamic direction, it should be a separate stage or part of this one?
            # v3 does dynamic direction based on momentum sign if enabled.
            # Let's check params
            if params.get("dynamic_direction", True):
                mom = features.loc[s, "momentum"] if s in features.index else 0.0
                meta["direction"] = "LONG" if mom >= 0 else "SHORT"

            winners.append(meta)

        context.winners = winners
        context.log_event(self.name, "SelectionComplete", {"stage": relaxation_stage, "n_winners": len(winners), "n_vetoed": len(disqualified)})

        return context

    def _apply_vetoes(self, features: pd.DataFrame, candidate_map: Dict[str, Any], settings: Any, params: Dict[str, Any]) -> Set[str]:
        disqualified = set()

        # Thresholds
        t_entropy = params.get("entropy_max_threshold", settings.features.entropy_max_threshold)
        t_efficiency = params.get("efficiency_min_threshold", settings.features.efficiency_min_threshold)

        for s in features.index:
            # 1. Metadata Vetoes
            meta = candidate_map.get(s, {})
            if any(f not in meta for f in ["tick_size", "lot_size", "price_precision"]):
                # Allow if benchmark? v3 logic exempts benchmarks.
                # Let's assume standard rigor first.
                pass

            # 2. Predictability Vetoes (if enabled)
            if settings.features.feat_predictability_vetoes:
                ent = features.loc[s, "entropy"]
                eff = features.loc[s, "efficiency"]

                if ent > t_entropy:
                    disqualified.add(s)
                if eff < t_efficiency:
                    disqualified.add(s)

            # 3. Regime Veto (Darwinian)
            # context.feature_store["survival"] is the prob, NOT the raw score?
            # v3 checks: if regime_all[s] < 0.1.
            # In FeatureEngineeringStage, 'survival' = regime_all. So yes.
            surv = features.loc[s, "survival"]
            if surv < 0.1:
                disqualified.add(s)

        # Benchmark Exemption
        for b in settings.benchmark_symbols:
            if b in disqualified:
                disqualified.remove(b)

        return disqualified
