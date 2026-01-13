import logging
from typing import Dict, Optional

import pandas as pd

from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.utils.scoring import calculate_mps_score, map_to_probability

logger = logging.getLogger("pipelines.selection.inference")


class InferenceStage(BasePipelineStage):
    """
    Stage 3: Conviction Scoring (Inference).
    Applies the Log-MPS (Multiplicative Probability Scoring) model to the Feature Store.
    """

    @property
    def name(self) -> str:
        return "Inference"

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        # Default Weights (v3.4 Standard)
        self.weights = weights or {"momentum": 1.0, "stability": 1.0, "liquidity": 1.0, "entropy": 1.0, "efficiency": 1.0, "hurst_clean": 1.0, "adx": 1.0, "survival": 1.0, "antifragility": 1.0}

        # Mapping Methods (v3.4 Standard)
        self.methods = {
            "survival": "cdf",
            "liquidity": "cdf",
            "momentum": "rank",
            "stability": "rank",
            "antifragility": "rank",
            "efficiency": "cdf",
            "entropy": "rank",
            "hurst_clean": "rank",
            "adx": "cdf",
        }

    def execute(self, context: SelectionContext) -> SelectionContext:
        features = context.feature_store
        if features.empty:
            logger.warning("InferenceStage: Feature store is empty. Skipping.")
            return context

        logger.info("Executing Log-MPS Inference...")

        # 1. Map Features to Probabilities
        # We only map features that exist in both the store and our config
        active_features = [f for f in features.columns if f in self.weights]

        # Helper: Get series for scoring
        # Note: We need separate Series dict for calculate_mps_score
        metrics_dict = {f: features[f] for f in active_features}

        # 2. Calculate Final Alpha Score
        # This reuses the validated logic from utils.scoring
        alpha_scores = calculate_mps_score(metrics=metrics_dict, weights=self.weights, methods=self.methods)

        # 3. Store Results
        # We store both the final score and the component probabilities for explainability
        outputs = pd.DataFrame(index=features.index)
        outputs["alpha_score"] = alpha_scores

        # Add component probabilities for audit
        for f in active_features:
            outputs[f"{f}_prob"] = map_to_probability(features[f], method=self.methods.get(f, "rank"))

        context.inference_outputs = outputs
        context.model_metadata = {"model": "Log-MPS-v4", "weights": self.weights, "methods": self.methods}

        context.log_event(self.name, "ScoringComplete", {"mean_score": float(alpha_scores.mean()), "max_score": float(alpha_scores.max())})

        return context
