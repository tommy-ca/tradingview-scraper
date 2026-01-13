import logging
from typing import Any, Dict, Optional

from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.stages.clustering import ClusteringStage
from tradingview_scraper.pipelines.selection.stages.feature_engineering import FeatureEngineeringStage
from tradingview_scraper.pipelines.selection.stages.inference import InferenceStage
from tradingview_scraper.pipelines.selection.stages.ingestion import IngestionStage
from tradingview_scraper.pipelines.selection.stages.policy import SelectionPolicyStage
from tradingview_scraper.pipelines.selection.stages.synthesis import SynthesisStage
from tradingview_scraper.settings import get_settings

logger = logging.getLogger("pipelines.selection.orchestrator")


class SelectionPipeline:
    """
    The Orchestrator for the MLOps-Centric Selection Pipeline (v4).
    Manages the Hierarchical Threshold Relaxation (HTR) loop and stage execution graph.
    """

    def __init__(self, run_id: str = "v4_run", candidates_path: str = "data/lakehouse/portfolio_candidates.json", returns_path: str = "data/lakehouse/portfolio_returns.csv"):
        self.run_id = run_id
        self.settings = get_settings()

        # Initialize Stages
        self.ingestion = IngestionStage(candidates_path=candidates_path, returns_path=returns_path)

        self.feature_eng = FeatureEngineeringStage()

        # Use production weights from global settings (v3 parity)
        weights = self.settings.features.weights_global.copy()
        # Ensure adx is present (v3 implicit default)
        if "adx" not in weights:
            weights["adx"] = 1.0

        self.inference = InferenceStage(weights=weights)
        self.clustering = ClusteringStage()
        self.policy = SelectionPolicyStage()
        self.synthesis = SynthesisStage()

    def run(self, overrides: Optional[Dict[str, Any]] = None) -> SelectionContext:
        """
        Execute the full selection pipeline with HTR loop.
        """
        logger.info(f"Starting Selection Pipeline Run: {self.run_id}")

        # 1. Initialize Context
        params = {
            "feature_lookback": 120,  # v3 Standard
            "cluster_threshold": 0.7,
            "max_clusters": 25,
            "top_n": 2,
        }
        if overrides:
            params.update(overrides)

        context = SelectionContext(run_id=self.run_id, params=params)

        # 2. Ingestion & Feature Engineering (Once)
        context = self.ingestion.execute(context)
        context = self.feature_eng.execute(context)

        # 3. HTR Loop (Policy Optimization)
        # Stages 1 to 4
        final_stage = 1
        for stage in [1, 2, 3, 4]:
            logger.info(f"--- HTR Stage {stage} ---")
            context.params["relaxation_stage"] = stage

            # Update thresholds for Stage 2 (Spectral Relaxation)
            if stage == 2:
                # v3 logic: min(1.0, t["entropy_max"] * 1.2), efficiency * 0.8
                base_ent = self.settings.features.entropy_max_threshold
                base_eff = self.settings.features.efficiency_min_threshold
                context.params["entropy_max_threshold"] = min(1.0, base_ent * 1.2)
                context.params["efficiency_min_threshold"] = base_eff * 0.8

            # Execute Core Loop
            # Note: We re-run Inference/Clustering only if parameters affecting them change.
            # Inference weights are static. Clustering params are static.
            # So theoretically we can run Inference/Clustering ONCE outside the loop?
            # Clustering depends on correlations. Correlations don't change.
            # Inference depends on features. Features don't change.
            # So ONLY Policy changes!

            # Optimization: Run Inference/Clustering ONCE if not already done
            if context.inference_outputs.empty:
                context = self.inference.execute(context)
            if not context.clusters:
                context = self.clustering.execute(context)

            # Policy Pruning
            context = self.policy.execute(context)

            # Check Exit Condition
            n_winners = len(context.winners)
            logger.info(f"Stage {stage} Candidates: {n_winners}")

            if n_winners >= 15:
                logger.info(f"Target pool size reached ({n_winners} >= 15). Exiting loop.")
                final_stage = stage
                break

            final_stage = stage

        # 4. Synthesis
        context = self.synthesis.execute(context)

        logger.info(f"Pipeline Complete. Selected {len(context.winners)} atoms at Stage {final_stage}.")
        return context
