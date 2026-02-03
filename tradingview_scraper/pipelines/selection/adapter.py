from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pandas as pd

from tradingview_scraper.pipelines.selection.pipeline import SelectionPipeline
from tradingview_scraper.selection_engines.base import BaseSelectionEngine, SelectionRequest, SelectionResponse

if TYPE_CHECKING:
    from tradingview_scraper.backtest.models import NumericalWorkspace

logger = logging.getLogger("pipelines.selection.adapter")


class SelectionPipelineAdapter(BaseSelectionEngine):
    """
    Adapter to bridge the MLOps-centric v4 SelectionPipeline to the
    legacy BaseSelectionEngine interface expected by BacktestOrchestrator.
    """

    @property
    def name(self) -> str:
        return "v4_pipeline"

    def __init__(self):
        super().__init__()
        self.pipeline = SelectionPipeline(run_id="v4_adapter_run")

    def select(
        self,
        returns: pd.DataFrame,
        raw_candidates: list[dict[str, Any]],
        stats_df: pd.DataFrame | None,
        request: SelectionRequest,
        workspace: NumericalWorkspace | None = None,
    ) -> SelectionResponse:
        """
        Executes the v4 pipeline and maps the result to SelectionResponse.
        """
        logger.info("Adapting v4 SelectionPipeline execution...")

        # Map Request Params
        overrides = {"top_n": request.top_n, "cluster_threshold": request.threshold, "max_clusters": request.max_clusters, **request.params}

        # Execute
        context = self.pipeline.run_with_data(returns_df=returns, raw_candidates=raw_candidates, overrides=overrides)

        # Map Output to SelectionResponse
        winner_syms = {w["symbol"] for w in context.winners}
        audit_clusters = {}

        for cid, syms in context.clusters.items():
            selected = [s for s in syms if s in winner_syms]
            audit_clusters[int(cid)] = {"size": len(syms), "selected": selected}

        # Map Metrics
        alpha_scores = context.inference_outputs["alpha_score"].to_dict() if not context.inference_outputs.empty else {}

        metrics = {"alpha_scores": alpha_scores, "raw_metrics": context.feature_store.to_dict() if not context.feature_store.empty else {}, "pipeline_audit": context.audit_trail}

        return SelectionResponse(winners=context.winners, audit_clusters=audit_clusters, spec_version="4.0-mlops", metrics=metrics, relaxation_stage=int(context.params.get("relaxation_stage", 1)))
