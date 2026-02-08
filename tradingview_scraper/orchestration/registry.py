import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class StageSpec:
    """Metadata for a registered pipeline stage."""

    id: str
    name: str
    description: str = ""
    category: str = ""  # "selection", "meta", "discovery", "risk"
    tags: List[str] = field(default_factory=list)
    params_schema: Optional[Type[BaseModel]] = None
    stage_class: Optional[Type] = None
    # New fields for v3.6+
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


class StageRegistry:
    """
    Central registry for all addressable pipeline stages.
    Enables discovery and dynamic invocation via URI.
    """

    _stages: Dict[str, Callable] = {}
    _specs: Dict[str, StageSpec] = {}

    @classmethod
    def register(cls, *args, **kwargs):
        """
        Register a stage. Can be used as a decorator or direct call.

        Usage 1 (New): StageRegistry.register(spec)
        Usage 2 (Old): @StageRegistry.register(id="...", ...)
        """
        # Usage 1: Direct registration with StageSpec
        if len(args) == 1 and isinstance(args[0], StageSpec) and not kwargs:
            spec = args[0]
            cls._specs[spec.id] = spec
            if spec.stage_class:
                cls._stages[spec.id] = spec.stage_class
            return

        # Usage 2: Decorator factory (Legacy/Existing)
        # Arguments from kwargs or args
        id_val = kwargs.get("id")
        if not id_val and args and isinstance(args[0], str):
            id_val = args[0]

        name = kwargs.get("name")
        description = kwargs.get("description", "")
        category = kwargs.get("category", "")
        tags = kwargs.get("tags", [])
        params_schema = kwargs.get("params_schema")

        if not id_val:
            raise ValueError("Stage ID is required")

        if name is None:
            name = id_val  # Fallback name to ID if not provided

        def decorator(func_or_cls: Callable):
            cls._stages[id_val] = func_or_cls
            cls._specs[id_val] = StageSpec(
                id=id_val,
                name=name,
                description=description,
                category=category,
                tags=tags or [],
                params_schema=params_schema,
                stage_class=func_or_cls if isinstance(func_or_cls, type) else None,
            )
            return func_or_cls

        return decorator

    @classmethod
    def register_class(cls, spec: StageSpec):
        """Decorator to register a class with a pre-defined StageSpec."""

        def decorator(stage_cls: Type):
            # Update the spec with the class if not set
            if spec.stage_class is None:
                spec.stage_class = stage_cls

            # Register
            cls._specs[spec.id] = spec
            cls._stages[spec.id] = stage_cls
            return stage_cls

        return decorator

    @classmethod
    def get(cls, id: str) -> StageSpec:
        """Get stage specification by ID."""
        return cls.get_spec(id)

    @classmethod
    def get_stage(cls, id: str) -> Callable:
        cls._ensure_loaded()
        if id not in cls._stages:
            raise KeyError(f"Stage '{id}' not found in registry.")
        return cls._stages[id]

    @classmethod
    def get_spec(cls, id: str) -> StageSpec:
        cls._ensure_loaded()
        if id not in cls._specs:
            raise KeyError(f"Stage '{id}' not found in registry.")
        return cls._specs[id]

    @classmethod
    def list_stages(cls, tag: Optional[str] = None, category: Optional[str] = None) -> List[StageSpec]:
        # Ensure common stages are loaded
        cls._ensure_loaded()

        results = list(cls._specs.values())
        if tag:
            results = [s for s in results if tag in s.tags]
        if category:
            results = [s for s in results if s.category == category]
        return results

    @classmethod
    def _ensure_loaded(cls):
        """Internal helper to ensure core stage modules are imported."""
        if hasattr(cls, "_loaded") and cls._loaded:
            return

        import importlib
        import pkgutil

        import tradingview_scraper.pipelines

        # 1. Discover all modules in pipelines package
        try:
            for loader, module_name, is_pkg in pkgutil.walk_packages(tradingview_scraper.pipelines.__path__, tradingview_scraper.pipelines.__name__ + "."):
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    logger.warning(f"StageRegistry: Failed to load pipeline module {module_name}: {e}")
        except Exception as e:
            logger.warning(f"StageRegistry: Failed to walk packages: {e}")

        # 2. Specifically load script modules that register stages
        script_modules = [
            "scripts.build_meta_returns",
            "scripts.optimize_meta_portfolio",
            "scripts.flatten_meta_weights",
            "scripts.generate_meta_report",
            "scripts.optimize_clustered_v2",
            "scripts.synthesize_strategy_matrix",
            "scripts.services.backfill_features",
        ]
        for mod in script_modules:
            try:
                importlib.import_module(mod)
            except Exception as e:
                # scripts might not be a package or in path depending on how tests run
                logger.warning(f"StageRegistry: Failed to load script module {mod}: {e}")

        cls._loaded = True
