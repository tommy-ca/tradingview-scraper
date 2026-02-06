from __future__ import annotations

import json
import logging
import functools
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import pandas as pd
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger("pipelines.selection")


class SelectionContext(BaseModel):
    """
    The state container for the Selection Pipeline.
    Passes through each stage, accumulating features and decisions.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str) -> str:
        """Strict whitelist for run_id to prevent path traversal (Phase 373)."""
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError(f"Invalid run_id format: {v}. Must be alphanumeric, underscores, or hyphens.")
        return v

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

    def merge(self, overlay: SelectionContext):
        """Merges another context into this one (additive and concatenation)."""
        import pandas as pd

        # Merge Feature Store (Concatenate distinct columns)
        if not overlay.feature_store.empty:
            if self.feature_store.empty:
                self.feature_store = overlay.feature_store
            else:
                # Only add new columns
                new_cols = overlay.feature_store.columns.difference(self.feature_store.columns)
                if not new_cols.empty:
                    self.feature_store = pd.concat([self.feature_store, overlay.feature_store[new_cols]], axis=1)

        # Merge Audit Trail (Append only new entries)
        if len(overlay.audit_trail) > len(self.audit_trail):
            new_entries = overlay.audit_trail[len(self.audit_trail) :]
            self.audit_trail.extend(new_entries)

        # Merge other fields if necessary (usually they are overridden by the last stage)
        if not overlay.returns_df.empty:
            self.returns_df = overlay.returns_df
        if overlay.raw_pool:
            self.raw_pool = overlay.raw_pool
        if overlay.inference_outputs:
            self.inference_outputs = overlay.inference_outputs
        if overlay.winners:
            self.winners = overlay.winners
        if overlay.strategy_atoms:
            self.strategy_atoms = overlay.strategy_atoms
        if overlay.composition_map:
            self.composition_map.update(overlay.composition_map)


def validate_io(func):
    """
    Decorator implementing the 'Filter & Log' strategy for pipeline stages.

    If validation fails, drop the invalid rows/symbols, log them to the audit trail,
    and proceed with the valid subset.
    """

    @functools.wraps(func)
    def wrapper(self, context: SelectionContext, *args, **kwargs) -> SelectionContext:
        # Execute the stage logic
        result_context = func(self, context, *args, **kwargs)

        # Check if the stage has validators defined
        validators = getattr(self, "validators", [])

        for field, validator_fn in validators:
            if not hasattr(result_context, field):
                continue

            data = getattr(result_context, field)

            # Currently supports DataFrame column filtering (symbols)
            if isinstance(data, pd.DataFrame):
                try:
                    # Expecting validator(df, strict=False) -> List[failed_keys]
                    failed_keys = validator_fn(data, strict=False)
                except TypeError:
                    # Fallback for validators without strict arg
                    failed_keys = validator_fn(data)

                if failed_keys:
                    logger.warning(f"[{self.name}] @validate_io: Dropping {len(failed_keys)} invalid items from '{field}' (Validator: {validator_fn.__name__})")

                    # Log to audit trail
                    result_context.log_event(
                        stage=self.name,
                        event="validation_filter",
                        data={
                            "field": field,
                            "validator": validator_fn.__name__,
                            "dropped_count": len(failed_keys),
                            "dropped_samples": failed_keys[:10],
                        },
                    )

                    # Filter the DataFrame (Keep columns that are NOT in failed_keys)
                    valid_cols = [c for c in data.columns if c not in failed_keys]
                    filtered_df = data[valid_cols]
                    setattr(result_context, field, filtered_df)

        return result_context

    return wrapper


class BasePipelineStage(ABC):
    """
    Abstract Base Class for all Pipeline Stages.
    Ensures statelessness and consistent interfaces.
    """

    @property
    def validators(self) -> List[Tuple[str, Callable[[Any], List[str]]]]:
        """
        Validators to apply after execution.
        Returns list of (context_field_name, validator_function).
        """
        return []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Automatically wrap the execute method of subclasses with @validate_io
        # This ensures the 'Filter & Log' strategy is enforced if validators are present.
        # We check if 'execute' is defined in the subclass or its MRO (excluding BasePipelineStage if possible,
        # but BasePipelineStage.execute is abstract so it shouldn't be callable in a way that matters,
        # actually abstract methods can be called via super()).

        # Note: cls.execute refers to the method that will be used.
        # If the subclass doesn't override execute (which it must as it's abstract), this might wrap the abstract one?
        # No, __init_subclass__ runs when the subclass is defined.
        if hasattr(cls, "execute") and callable(cls.execute):
            # Avoid double wrapping if possible (though unlikely here)
            if not getattr(cls.execute, "_is_validate_io_wrapped", False):
                cls.execute = validate_io(cls.execute)
                cls.execute._is_validate_io_wrapped = True

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
        Uses Pandera for formal schema enforcement (Phase 620).
        """
        from tradingview_scraper.pipelines.contracts import ReturnsMatrixSchema
        import pandera as pa

        if df.empty:
            return []

        try:
            # 1. Formal Schema Validation (Bounds, Index, Types)
            ReturnsMatrixSchema.validate(df)
        except Exception as e:
            # Using string comparison for the exception type to bypass module attribute LSP issues
            if e.__class__.__name__ == "SchemaError":
                logger.warning(f"Data Contract Violation in returns_matrix: {e}")
                if strict:
                    raise
            else:
                raise e

        failed_symbols = []
        for col in df.columns:
            series = df[col]
            # ... (Existing heuristic checks for padding) ...

            # 2. 'No Padding' Compliance (TradFi only)
            # Heuristic: If EXCHANGE is not BINANCE/OKX/etc, check weekends
            if ":" in str(col):
                exchange = str(col).split(":")[0].upper()
                is_crypto = exchange in ["BINANCE", "OKX", "BYBIT", "BITGET", "KUCOIN", "COINBASE", "KRAKEN"]

                if not is_crypto:
                    # Check for 0.0 exactly on weekends
                    # Use robust dayofweek check
                    try:
                        # Extract the dayofweek from the index
                        index_dt = pd.to_datetime(df.index)
                        # Use list comprehension to avoid DatetimeIndex/Index confusion in LSP
                        days = [t.dayofweek for t in index_dt]
                        weekends_mask = [d >= 5 for d in days]

                        if any(weekends_mask):
                            # Filter series
                            weekend_vals = series.iloc[weekends_mask].dropna()
                            if not weekend_vals.empty and (weekend_vals == 0.0).all():
                                logger.warning(f"IngestionValidator: {col} failed 'No Padding' standard (Zeroes found on weekends)")
                                failed_symbols.append(str(col))
                                continue
                    except Exception as e:
                        logger.warning(f"IngestionValidator: Could not check weekends for {col}: {e}")

        return failed_symbols


class AdvancedToxicityValidator:
    """
    Advanced Microstructure Toxicity Validator.
    Detects Volume Spikes and Price Stalls.
    """

    @staticmethod
    def is_volume_toxic(volume: pd.Series, sigma_threshold: float = 10.0) -> bool:
        """Detects if the latest volume bar is a statistical outlier (> 10 sigma)."""
        if len(volume) < 21:
            return False

        # Calculate trailing statistics (excluding latest)
        trailing = volume.iloc[:-1]
        mean_v = trailing.mean()
        std_v = trailing.std()

        if std_v == 0:
            return float(volume.iloc[-1]) > float(mean_v) * 2  # Simple multiplier fallback

        z_score = (float(volume.iloc[-1]) - float(mean_v)) / float(std_v)
        return bool(z_score > sigma_threshold)

    @staticmethod
    def is_price_stalled(prices: pd.Series, threshold: int = 3) -> bool:
        """Detects if price has been perfectly flat for N consecutive bars."""
        if len(prices) < threshold + 1:
            return False

        # Calculate diffs
        diffs = prices.diff().dropna()
        recent_diffs = diffs.tail(threshold)

        # If ALL recent diffs are EXACTLY zero
        return bool((recent_diffs == 0).all())


class FoundationHealthRegistry:
    """
    Manages the persistent health ledger for Lakehouse assets.
    """

    def __init__(self, path: Optional[Path] = None):
        from tradingview_scraper.settings import get_settings

        self.path = path or (get_settings().lakehouse_dir / "foundation_health.json")
        self.data: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load health registry: {e}")
                self.data = {}

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save health registry: {e}")

    def update_status(self, symbol: str, status: str, **metrics):
        self.data[symbol] = {
            "status": status,
            "last_audit": datetime.now().isoformat(),
            **metrics,
        }

    def is_healthy(self, symbol: str) -> bool:
        return self.data.get(symbol, {}).get("status") == "healthy"
