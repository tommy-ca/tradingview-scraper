from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, cast

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
    trace_id: Optional[str] = None
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


class IngestionValidator:
    """
    L1 Data Contract Validator.
    Enforces institutional standards: Toxicity bounds and 'No Padding'.
    """

    @staticmethod
    def validate_returns(df: pd.DataFrame, strict: bool = False) -> List[str]:
        """
        Validates returns matrix against toxicity and padding rules.
        Returns a list of symbols that FAILED validation.
        """
        failed_symbols = []

        if df.empty:
            return []

        for col in df.columns:
            series = df[col]

            # 1. Toxicity Bound (> 500% daily return)
            if (series.abs() > 5.0).any():
                logger.warning(f"IngestionValidator: {col} is TOXIC (|r| > 500%)")
                failed_symbols.append(str(col))
                continue

            # 2. 'No Padding' Compliance (TradFi only)
            # Heuristic: If EXCHANGE is not BINANCE/OKX/etc, check weekends
            if ":" in str(col):
                exchange = str(col).split(":")[0].upper()
                is_crypto = exchange in ["BINANCE", "OKX", "BYBIT", "BITGET", "KUCOIN", "COINBASE", "KRAKEN"]

                if not is_crypto:
                    # Check for 0.0 exactly on weekends
                    # Use robust dayofweek check
                    try:
                        days = pd.to_datetime(df.index).dayofweek
                        weekends_mask = days >= 5
                        if weekends_mask.any():
                            weekend_vals = series[weekends_mask].dropna()
                            if not weekend_vals.empty and (weekend_vals == 0.0).all():
                                logger.warning(f"IngestionValidator: {col} failed 'No Padding' standard (Zeroes found on weekends)")
                                failed_symbols.append(str(col))
                                continue
                    except Exception as e:
                        logger.warning(f"IngestionValidator: Could not check weekends for {col}: {e}")

        return failed_symbols
