import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class StageSpec:
    """Metadata for a registered pipeline stage."""

    id: str
    name: str
    description: str
    category: str  # "selection", "meta", "discovery", "risk"
    tags: List[str] = field(default_factory=list)
    params_schema: Optional[Type[BaseModel]] = None
    stage_class: Optional[Type] = None


class StageRegistry:
    """
    Central registry for all addressable pipeline stages.
    Enables discovery and dynamic invocation via URI.
    """

    _stages: Dict[str, Callable] = {}
    _specs: Dict[str, StageSpec] = {}

    @classmethod
    def register(cls, id: str, name: str, description: str, category: str, tags: Optional[List[str]] = None, params_schema: Optional[Type[BaseModel]] = None):
        """Decorator for registering a stage function or class."""

        def decorator(func_or_cls: Callable):
            cls._stages[id] = func_or_cls
            cls._specs[id] = StageSpec(
                id=id, name=name, description=description, category=category, tags=tags or [], params_schema=params_schema, stage_class=func_or_cls if isinstance(func_or_cls, type) else None
            )
            return func_or_cls

        return decorator

    @classmethod
    def get_stage(cls, id: str) -> Callable:
        if id not in cls._stages:
            raise KeyError(f"Stage '{id}' not found in registry.")
        return cls._stages[id]

    @classmethod
    def get_spec(cls, id: str) -> StageSpec:
        if id not in cls._specs:
            raise KeyError(f"Stage '{id}' not found in registry.")
        return cls._specs[id]

    @classmethod
    def list_stages(cls, tag: Optional[str] = None, category: Optional[str] = None) -> List[StageSpec]:
        results = list(cls._specs.values())
        if tag:
            results = [s for s in results if tag in s.tags]
        if category:
            results = [s for s in results if s.category == category]
        return results
