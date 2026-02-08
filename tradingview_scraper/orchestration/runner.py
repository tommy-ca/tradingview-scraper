import logging
import os
from typing import Any, List, Union, Optional

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.orchestration.cleanup import cleanup_zombies
from tradingview_scraper.telemetry.tracing import trace_span

logger = logging.getLogger(__name__)


class DAGRunner:
    """
    Orchestrates the execution of a Directed Acyclic Graph (DAG) of pipeline stages.
    Supports sequential and parallel branch execution.
    """

    def __init__(self, steps: List[Union[str, List[str]]], pipeline_name: Union[str, None] = None):
        """
        Args:
            steps: A list of stage IDs or sub-lists of stage IDs (for parallel execution).
            pipeline_name: Optional name of the pipeline (used for Prefect flow resolution).
        """
        self.steps = steps
        self.pipeline_name = pipeline_name

    @trace_span("dag.execute")
    def execute(self, context: Any) -> Any:
        """
        Executes the DAG using the provided context.
        Returns the final transformed context.
        """
        # Check for Prefect orchestration mode
        if os.getenv("TV_ORCH_MODE") == "prefect" and self.pipeline_name:
            try:
                return self._run_prefect_flow(context)
            except Exception as e:
                logger.warning(f"Prefect execution failed or not available: {e}. Falling back to default runner.")

        logger.info(f"DAGRunner: Starting execution with {len(self.steps)} steps")

        current_context = context

        try:
            for step in self.steps:
                if isinstance(step, str):
                    # Sequential Stage
                    current_context = self._run_stage(step, current_context)
                elif isinstance(step, list):
                    # Parallel Branches
                    current_context = self._run_parallel(step, current_context)
                else:
                    raise TypeError(f"Invalid step type: {type(step)}")

            logger.info("DAGRunner: Execution complete")
            return current_context

        finally:
            cleanup_zombies()

    def _run_prefect_flow(self, context: Any) -> Any:
        """Executes the corresponding Prefect flow for the pipeline."""
        logger.info(f"DAGRunner: Delegating execution to Prefect for pipeline '{self.pipeline_name}'")

        if self.pipeline_name.startswith("alpha."):
            from tradingview_scraper.orchestration.flows.selection import run_selection_flow

            # Extract arguments from SelectionContext
            run_id = getattr(context, "run_id", None)
            params = getattr(context, "params", {})

            # Fallback for dict context
            if isinstance(context, dict):
                run_id = context.get("run_id")
                params = context.get("params", {})

            # Prepare kwargs to avoid duplicate arguments
            kwargs = params.copy() if isinstance(params, dict) else {}
            profile = kwargs.pop("profile", "production")

            return run_selection_flow(profile=profile, run_id=run_id, **kwargs)

        elif self.pipeline_name.startswith("meta."):
            from tradingview_scraper.orchestration.flows.meta import run_meta_flow

            run_id = getattr(context, "run_id", None)
            meta_profile = getattr(context, "meta_profile", "meta_production")
            sleeve_profiles = getattr(context, "sleeve_profiles", None)

            # Fallback for dict context
            if isinstance(context, dict):
                run_id = context.get("run_id")
                params = context.get("params", {})
                meta_profile = params.get("profile", "meta_production")
                sleeve_profiles = params.get("profiles", [])

            return run_meta_flow(meta_profile=meta_profile, run_id=run_id, profiles=sleeve_profiles)

        else:
            raise ValueError(f"No Prefect flow mapped for pipeline: {self.pipeline_name}")

    def _run_stage(self, stage_id: str, context: Any) -> Any:
        """Executes a single stage via the SDK logic."""
        from tradingview_scraper.orchestration.sdk import QuantSDK

        # We use the internal implementation to avoid nested dag.execute spans
        # if run_stage itself is decorated (which it is via QuantSDK).
        # Actually, QuantSDK._run_stage_impl is what we want.
        return QuantSDK.run_stage(stage_id, context=context)

    def _run_parallel(self, branch_ids: List[str], context: Any) -> Any:
        """Executes multiple stages in parallel using Ray if available."""
        import copy

        use_parallel = os.getenv("TV_ORCH_PARALLEL") == "1"

        if not use_parallel:
            logger.info(f"DAGRunner: Executing {len(branch_ids)} branches sequentially (TV_ORCH_PARALLEL != 1)")
            for stage_id in branch_ids:
                # We work on copies to simulate parallel isolation
                branch_ctx = copy.deepcopy(context)
                branch_res = self._run_stage(stage_id, branch_ctx)
                context = self._merge_contexts(context, branch_res)
            return context

        # Ray execution for parallel branches
        from tradingview_scraper.orchestration.compute import RayComputeEngine
        import ray

        logger.info(f"DAGRunner: Dispatching {len(branch_ids)} branches to Ray")

        @ray.remote
        def execute_remote(sid: str, ctx: Any):
            from tradingview_scraper.orchestration.sdk import QuantSDK

            return QuantSDK.run_stage(sid, context=ctx)

        with RayComputeEngine() as engine:
            engine.ensure_initialized()
            futures = [execute_remote.remote(sid, copy.deepcopy(context)) for sid in branch_ids]
            results = ray.get(futures)

            for res in results:
                context = self._merge_contexts(context, res)

        return context

    def _merge_contexts(self, base: Any, overlay: Any) -> Any:
        """Merges two context objects using polymorphic delegation."""
        if base is None:
            return overlay

        # Polymorphic Merge (New)
        if hasattr(base, "merge") and callable(getattr(base, "merge")):
            base.merge(overlay)
            return base

        # Fallback for Dict-based context (for generic/test steps)
        if isinstance(base, dict) and isinstance(overlay, dict):
            for k, v in overlay.items():
                if k in base and isinstance(base[k], list) and isinstance(v, list):
                    # List suffix merge (like audit trails)
                    if len(v) > len(base[k]):
                        new_items = v[len(base[k]) :]
                        base[k].extend(new_items)
                else:
                    base[k] = v
            return base

        # Fallback: override base with overlay
        return overlay
