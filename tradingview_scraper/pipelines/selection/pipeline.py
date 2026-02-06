import logging
from typing import Any, Dict, Optional

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.stages.clustering import ClusteringStage
from tradingview_scraper.pipelines.selection.stages.feature_engineering import FeatureEngineeringStage
from tradingview_scraper.pipelines.selection.stages.inference import InferenceStage
from tradingview_scraper.pipelines.selection.stages.ingestion import IngestionStage
from tradingview_scraper.pipelines.selection.stages.policy import SelectionPolicyStage
from tradingview_scraper.pipelines.selection.stages.synthesis import SynthesisStage
from tradingview_scraper.settings import get_settings

logger = logging.getLogger("pipelines.selection.orchestrator")


@StageRegistry.register(id="alpha.selection_v4", name="Selection Pipeline v4", description="HTR selection pipeline with 4-stage relaxation", category="alpha")
class SelectionPipeline:
    """
    The Orchestrator for the MLOps-Centric Selection Pipeline (v4).
    Manages the Hierarchical Threshold Relaxation (HTR) loop and stage execution graph.
    """

    def __init__(self, run_id: str = "v4_run", candidates_path: str | None = None, returns_path: str | None = None):
        self.run_id = run_id
        self.settings = get_settings()

        # Initialize Stages
        self.ingestion = IngestionStage(candidates_path=candidates_path, returns_path=returns_path)

        self.feature_eng = FeatureEngineeringStage()

        # Use production weights from global settings (v3 parity)
        weights = self.settings.features.weights_global.copy()

        # Apply Profile-Specific Weight Overrides (Custom MPS Plan 2026-01-16)
        if self.settings.features.mps_weights_override:
            overrides = self.settings.features.mps_weights_override
            logger.info(f"Applying MPS Weight Overrides: {overrides}")
            weights.update(overrides)

        # Apply Signal Dominance Override (v4.1)
        # Allows profiles to declare a "primary" signal that overrides the default ensemble
        dom_signal = self.settings.features.dominant_signal
        dom_weight = self.settings.features.dominant_signal_weight

        if dom_signal and dom_signal in weights:
            logger.info(f"Applying Signal Dominance: {dom_signal} = {dom_weight}")
            # Boost the dominant signal
            weights[dom_signal] = dom_weight

            # Dampen Momentum if it's not the dominant signal
            # This prevents momentum drift from overshadowing the target signal
            if dom_signal != "momentum" and "momentum" in weights:
                logger.info("Dampening Momentum weight due to signal dominance.")
                weights["momentum"] = 0.5  # Reduced from ~1.75

        # Ensure adx is present (v3 implicit default)
        if "adx" not in weights:
            weights["adx"] = 1.0

        self.inference = InferenceStage(weights=weights)
        self.clustering = ClusteringStage()
        self.policy = SelectionPolicyStage()
        self.synthesis = SynthesisStage()

    def _execute_htr_loop(self, context: SelectionContext) -> SelectionContext:
        """Executes the Hierarchical Threshold Relaxation (HTR) loop."""
        req_stage = int(context.params.get("relaxation_stage", 0))
        final_stage = 1

        for stage in [1, 2, 3, 4]:
            if req_stage > 0 and stage != req_stage:
                continue

            logger.info(f"--- HTR Stage {stage} ---")
            context.params["relaxation_stage"] = stage

            # CR-490: Entropy-Aware Hardening
            if not context.feature_store.empty:
                avg_entropy = float(context.feature_store["entropy"].mean())
                if avg_entropy > 0.95:
                    logger.warning(f"High-Entropy Regime detected ({avg_entropy:.4f}). Tightening vetoes.")
                    base_ent = context.params.get("entropy_max_threshold", self.settings.features.entropy_max_threshold)
                    context.params["entropy_max_threshold"] = base_ent * 0.9

            if stage == 2:
                base_ent = self.settings.features.entropy_max_threshold
                base_eff = self.settings.features.efficiency_min_threshold
                context.params["entropy_max_threshold"] = min(1.0, base_ent * 1.2)
                context.params["efficiency_min_threshold"] = base_eff * 0.8

            # Execute Core Stages (Optimized: only Inference/Clustering once)
            if context.inference_outputs.empty:
                context = self.inference.execute(context)
            if not context.clusters:
                context = self.clustering.execute(context)

            context = self.policy.execute(context)

            n_winners = len(context.winners)
            if n_winners >= 15:
                final_stage = stage
                break

            final_stage = stage
            if req_stage > 0:
                break

        return self.synthesis.execute(context)

    def run_with_data(self, returns_df: Any, raw_candidates: Any, overrides: Optional[Dict[str, Any]] = None) -> SelectionContext:
        """
        Execute pipeline with in-memory data (Adapter Mode).
        Bypasses IngestionStage file loading.
        """
        logger.info(f"Starting Selection Pipeline Run (Adapter Mode): {self.run_id}")

        params = {
            "feature_lookback": self.settings.features.feature_lookback,
            "cluster_threshold": 0.7,
            "max_clusters": 25,
            "top_n": self.settings.top_n,
        }
        if overrides:
            params.update(overrides)

        context = SelectionContext(run_id=self.run_id, params=params)
        context.returns_df = returns_df
        context.raw_pool = raw_candidates
        context.log_event("Ingestion", "DataInjected", {"n_candidates": len(raw_candidates)})

        context = self.feature_eng.execute(context)
        return self._execute_htr_loop(context)

    def run(self, overrides: Optional[Dict[str, Any]] = None) -> SelectionContext:
        """Execute the full selection pipeline with HTR loop."""
        logger.info(f"Starting Selection Pipeline Run: {self.run_id}")

        params = {
            "feature_lookback": self.settings.features.feature_lookback,
            "cluster_threshold": 0.7,
            "max_clusters": 25,
            "top_n": self.settings.top_n,
        }
        if overrides:
            params.update(overrides)

        context = SelectionContext(run_id=self.run_id, params=params)
        context = self.ingestion.execute(context)
        context = self.feature_eng.execute(context)

        return self._execute_htr_loop(context)
