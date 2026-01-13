from __future__ import annotations

from typing import Dict, Type

from tradingview_scraper.selection_engines.base import BaseSelectionEngine, SelectionRequest, SelectionResponse, get_hierarchical_clusters, get_robust_correlation

from .impl.baseline import BaselineSelectionEngine
from .impl.v2_cars import SelectionEngineV2, SelectionEngineV2_0, SelectionEngineV2_1
from .impl.v3_4_htr import SelectionEngineV3_4
from .impl.v3_mps import SelectionEngineV3, SelectionEngineV3_1, SelectionEngineV3_2

SELECTION_ENGINES: Dict[str, Type[BaseSelectionEngine]] = {
    "v2.0": SelectionEngineV2_0,
    "v2": SelectionEngineV2,
    "v2.1": SelectionEngineV2_1,
    "v3": SelectionEngineV3,
    "v3.1": SelectionEngineV3_1,
    "v3.2": SelectionEngineV3_2,
    "v3.4": SelectionEngineV3_4,
    "baseline": BaselineSelectionEngine,
    "legacy": SelectionEngineV2_0,  # Alias for backward compatibility
}


def list_known_selection_engines() -> list[str]:
    return sorted(SELECTION_ENGINES.keys())


def build_selection_engine(name: str) -> BaseSelectionEngine:
    """
    Factory to recruit a selection engine by version name.
    """
    key = name.strip().lower()
    if key not in SELECTION_ENGINES:
        raise ValueError(f"Unknown selection engine: {name}")

    return SELECTION_ENGINES[key]()


__all__ = [
    "BaseSelectionEngine",
    "SelectionRequest",
    "SelectionResponse",
    "get_robust_correlation",
    "get_hierarchical_clusters",
    "build_selection_engine",
    "list_known_selection_engines",
]
