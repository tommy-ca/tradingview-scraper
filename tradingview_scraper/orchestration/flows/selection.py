from typing import Any, Dict, Optional

from prefect import flow, task
from prefect.context import get_run_context

from tradingview_scraper.orchestration.cleanup import cleanup_zombies
from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.settings import ThreadSafeConfig, get_settings
from tradingview_scraper.telemetry.mlflow_tracker import MLflowTracker
from tradingview_scraper.telemetry.tracing import trace_span


def _get_stage_runner(stage_id: str):
    """
    Helper to resolve and instantiate a stage from the registry.
    """
    spec = StageRegistry.get_spec(stage_id)
    if spec.stage_class:
        # Instantiate class-based stage
        return spec.stage_class()
    else:
        # Return function-based stage
        return StageRegistry.get_stage(stage_id)


@task(name="Ingestion", retries=2)
def task_ingestion(context: SelectionContext) -> SelectionContext:
    runner = _get_stage_runner("foundation.ingest")
    if hasattr(runner, "execute"):
        return runner.execute(context)
    return runner(context=context)


@task(name="Feature Engineering")
def task_features(context: SelectionContext) -> SelectionContext:
    runner = _get_stage_runner("foundation.features")
    if hasattr(runner, "execute"):
        return runner.execute(context)
    return runner(context=context)


@task(name="Inference")
def task_inference(context: SelectionContext) -> SelectionContext:
    runner = _get_stage_runner("alpha.inference")
    if hasattr(runner, "execute"):
        return runner.execute(context)
    return runner(context=context)


@task(name="Clustering")
def task_clustering(context: SelectionContext) -> SelectionContext:
    runner = _get_stage_runner("alpha.clustering")
    if hasattr(runner, "execute"):
        return runner.execute(context)
    return runner(context=context)


@task(name="Policy (Relaxation)")
def task_policy(context: SelectionContext, relaxation_stage: int) -> SelectionContext:
    # Update context params for relaxation stage
    context.params["relaxation_stage"] = relaxation_stage

    runner = _get_stage_runner("alpha.policy")
    if hasattr(runner, "execute"):
        return runner.execute(context)
    return runner(context=context)


@task(name="Synthesis")
def task_synthesis(context: SelectionContext) -> SelectionContext:
    runner = _get_stage_runner("alpha.synthesis")
    if hasattr(runner, "execute"):
        return runner.execute(context)
    return runner(context=context)


@flow(name="Selection Flow (v4 HTR)")
def run_selection_flow(profile: str = "production", run_id: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None) -> SelectionContext:
    """
    Main Prefect Flow for the Alpha Selection Pipeline.
    Implements the v4 Hierarchical Threshold Relaxation (HTR) Loop.

    Stages:
    1. Ingestion: Load raw market data
    2. Features: Generate factors and signals
    3. Inference: Run models / compute alpha scores
    4. Clustering: Group assets by correlation/regime
    5. HTR Loop (Policy):
       - Stage 1: Strict (High thresholds)
       - Stage 2: Spectral (Regime-aware)
       - Stage 3: Cluster Floor (Ensures diversity)
       - Stage 4: Alpha Fallback (Min constraints)
    6. Synthesis: Construct strategy atoms
    """
    # 1. Initialize Configuration
    settings = get_settings().clone(profile=profile)
    if run_id:
        settings.run_id = run_id
    if overrides:
        settings = settings.clone(**overrides)

    # Set thread-local config for this flow run
    token = ThreadSafeConfig.set_active(settings)

    # Initialize Telemetry
    tracker = MLflowTracker(experiment_name=f"selection_{profile}")
    tracker.log_params(settings.model_dump())

    try:
        # 2. Initialize Context
        ctx = SelectionContext(run_id=settings.run_id, params=settings.model_dump())

        # 3. Execution Pipeline
        ctx = task_ingestion(ctx)
        ctx = task_features(ctx)
        ctx = task_inference(ctx)
        ctx = task_clustering(ctx)

        # 4. HTR Loop Implementation
        # We iterate through relaxation stages until we satisfy the winner count
        min_winners = 15  # Hardcoded SSP floor as per docs, or could be in settings

        for stage in [1, 2, 3, 4]:
            tracker.log_metrics({"htr_stage": stage})
            ctx = task_policy(ctx, relaxation_stage=stage)

            num_winners = len(ctx.winners)
            tracker.log_metrics({f"stage_{stage}_winners": num_winners})

            if num_winners >= min_winners:
                print(f"HTR Satisfied at Stage {stage} with {num_winners} winners.")
                break
        else:
            print(f"HTR Warning: Completed all stages with only {len(ctx.winners)} winners.")

        # 5. Synthesis
        ctx = task_synthesis(ctx)

        tracker.log_metrics({"final_atoms": len(ctx.strategy_atoms)})
        return ctx

    finally:
        cleanup_zombies()
        # Cleanup thread-local config
        ThreadSafeConfig.reset_active(token)
