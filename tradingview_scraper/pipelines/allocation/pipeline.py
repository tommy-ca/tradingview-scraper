import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.allocation.base import AllocationContext
from tradingview_scraper.pipelines.allocation.stages.optimization import OptimizationStage
from tradingview_scraper.pipelines.allocation.stages.simulation import SimulationStage
from tradingview_scraper.risk.engine import RiskManagementEngine
from tradingview_scraper.selection_engines import get_hierarchical_clusters
from tradingview_scraper.settings import get_settings

logger = logging.getLogger("pipelines.allocation.orchestrator")


@StageRegistry.register(id="pillar3.allocation_v1", name="Allocation Pipeline v1", description="Modular Pillar 3 Allocation & Simulation Pipeline", category="allocation")
class AllocationPipeline:
    """
    The Orchestrator for the Pillar 3: Portfolio Allocation Pipeline.
    Manages optimization across multiple engines/profiles and runs simulators.
    """

    def __init__(self):
        self.settings = get_settings()
        self.optimization = OptimizationStage()
        self.simulation = SimulationStage()
        self.risk_engine = RiskManagementEngine(self.settings)

    def run(self, context: AllocationContext) -> AllocationContext:
        """
        Executes the allocation and simulation sequence for a window.
        """
        # 1. Sync Risk State for current window
        # We estimate current equity from last holdings if available
        current_equity = context.current_holdings.get("total_equity", self.settings.initial_capital)
        self.risk_engine.sync_daily_state(
            equity=current_equity,
            balance=context.starting_balance,
            ledger=context.ledger,  # Pass ledger for shadow snapshot recovery
        )

        # 2. Clustering (Pillar 3 specific on synthesized returns)
        context = self._execute_clustering(context)

        # 2. Iterate Engines & Profiles
        for engine_name in context.engine_names:
            profiles_to_run = ["adaptive"] if engine_name == "adaptive" else context.profiles
            for profile in profiles_to_run:
                # A. Optimization
                weights_df = self.optimization.execute(context, engine_name, profile)

                if weights_df.empty:
                    logger.warning(f"Skipping simulation for {engine_name}/{profile} due to empty weights.")
                    continue

                # B. Simulation
                for sim_name in context.sim_names:
                    context = self.simulation.execute(context, sim_name, engine_name, profile, weights_df)

        return context

    def _execute_clustering(self, context: AllocationContext) -> AllocationContext:
        """Performs hierarchical clustering on synthesized return streams."""
        if context.train_rets_strat.empty:
            return context

        try:
            new_cluster_ids, _ = get_hierarchical_clusters(context.train_rets_strat, float(self.settings.threshold), 25)
            stringified_clusters = {}
            for sym, c_id in zip(context.train_rets_strat.columns, new_cluster_ids):
                stringified_clusters.setdefault(str(c_id), []).append(str(sym))

            # Update context with new clusters
            # Note: context is a pydantic model, so we can just update the field
            context.clusters.update(stringified_clusters)

        except Exception as e:
            logger.error(f"Clustering failed in AllocationPipeline: {e}")

        return context
