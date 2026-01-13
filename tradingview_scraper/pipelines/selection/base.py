from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("pipelines.selection")


class SelectionContext(BaseModel):
    """
    The state container for the Selection Pipeline.
    Passes through each stage, accumulating features and decisions.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    params: Dict[str, Any] = Field(default_factory=dict)

    # Stage 1: Ingestion
    raw_pool: List[Dict[str, Any]] = Field(default_factory=list)
    returns_df: pd.DataFrame = Field(default_factory=pd.DataFrame)

    # Stage 2: Feature Engineering
    feature_store: pd.DataFrame = Field(default_factory=pd.DataFrame)

    # Stage 3: Inference
    inference_outputs: pd.DataFrame = Field(default_factory=pd.DataFrame)
    model_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Stage 4: Partitioning
    clusters: Dict[int, List[str]] = Field(default_factory=dict)

    # Stage 5: Policy Pruning
    winners: List[Dict[str, Any]] = Field(default_factory=list)

    # Stage 6: Synthesis
    strategy_atoms: List[Any] = Field(default_factory=list)  # List[StrategyAtom]
    composition_map: Dict[str, Dict[str, float]] = Field(default_factory=dict)

    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)

    def log_event(self, stage: str, event: str, data: Optional[Dict[str, Any]] = None):
        self.audit_trail.append({"stage": stage, "event": event, "data": data or {}})


class BasePipelineStage(ABC):
    """
    Abstract Base Class for all Pipeline Stages.
    Ensures statelessness and consistent interfaces.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Friendly name of the stage."""
        pass

    @abstractmethod
    def execute(self, context: SelectionContext) -> SelectionContext:
        """
        Main execution logic for the stage.
        Must return the modified (enriched) context.
        """
        pass
