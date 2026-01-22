import logging
from typing import Any, Optional

from tradingview_scraper.orchestration.registry import StageRegistry

logger = logging.getLogger(__name__)


class QuantSDK:
    """
    High-level API for interacting with the quantitative portfolio platform.
    Used by Claude skills and CLI.
    """

    @staticmethod
    def run_stage(id: str, context: Optional[Any] = None, **params) -> Any:
        """
        Executes a single pipeline stage by its ID.
        """
        logger.info(f"SDK: Executing stage {id}")
        stage_callable = StageRegistry.get_stage(id)
        spec = StageRegistry.get_spec(id)

        # If it's a class (BasePipelineStage), instantiate and execute
        if spec.stage_class:
            instance = spec.stage_class(**params)
            if context is None:
                # Some stages might create their own context if needed
                # but for selection stages, it's usually required.
                pass
            return instance.execute(context)

        # If it's a function/method
        # Functions might not take 'context' as first arg, but we'll try to be flexible
        # If context is provided, we could pass it, but meta functions currently don't use it.
        # Let's check the signature if possible or just call with params.
        import inspect

        sig = inspect.signature(stage_callable)
        if "context" in sig.parameters:
            return stage_callable(context=context, **params)
        else:
            return stage_callable(**params)

    @staticmethod
    def run_pipeline(name: str, profile: str, run_id: Optional[str] = None, **overrides) -> Any:
        """
        Executes a full named pipeline (e.g., 'selection.full').
        """
        logger.info(f"SDK: Running pipeline {name} for profile {profile}")
        # (This will be implemented as we migrate full pipelines to the new orchestrator)
        pass
