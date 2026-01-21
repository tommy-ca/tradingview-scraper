import logging
from typing import Any, Dict, Optional

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import SelectionContext

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

        # If it's a class (BasePipelineStage), instantiate and execute
        if isinstance(stage_callable, type):
            # For BasePipelineStage implementations
            instance = stage_callable(**params)
            if context is None:
                raise ValueError(f"Stage {id} requires a context object.")
            return instance.execute(context)

        # If it's a function/method
        return stage_callable(context, **params)

    @staticmethod
    def run_pipeline(name: str, profile: str, run_id: Optional[str] = None, **overrides) -> Any:
        """
        Executes a full named pipeline (e.g., 'selection.full').
        """
        logger.info(f"SDK: Running pipeline {name} for profile {profile}")
        # (This will be implemented as we migrate full pipelines to the new orchestrator)
        pass
